import json, subprocess, copy

GATEWAY = "odhappsprd-agw"
RG = "odhapps-prd-shared-rg"
FILE = "environmentDefaults.json"

# --- 1. Pull full live prod gateway ---
result = subprocess.run(
    ["az", "network", "application-gateway", "show",
     "--name", GATEWAY, "--resource-group", RG, "-o", "json"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print("az failed:", result.stderr); exit(1)

gw = json.loads(result.stdout)
p = gw.get("properties", gw)

def last_seg(resource_id):
    return resource_id.rstrip("/").split("/")[-1] if resource_id else None

# --- 2. Transform ARM format -> your flat structure ---
# Adjust field names to match exactly what your bicep/defaults expect
frontendPorts = sorted(
    [{"name": x["name"], "port": x["properties"]["port"]} for x in p.get("frontendPorts", [])],
    key=lambda r: r["port"])

backendAddressPools = [
    {"name": x["name"],
     "backendAddresses": x["properties"].get("backendAddresses", [])}
    for x in p.get("backendAddressPools", [])]

httpListeners = [
    {"name": x["name"],
     "frontendPortName": last_seg(x["properties"].get("frontendPort", {}).get("id")),
     "protocol": x["properties"].get("protocol"),
     "hostName": x["properties"].get("hostName", ""),
     "sslCertificateName": last_seg(x["properties"].get("sslCertificate", {}).get("id")) if x["properties"].get("sslCertificate") else "",
     "requireServerNameIndication": x["properties"].get("requireServerNameIndication", False)}
    for x in p.get("httpListeners", [])]

requestRoutingRules = [
    {"name": x["name"],
     "ruleType": x["properties"].get("ruleType"),
     "priority": x["properties"].get("priority"),
     "httpListenerName": last_seg(x["properties"].get("httpListener", {}).get("id")),
     "backendAddressPoolName": last_seg(x["properties"].get("backendAddressPool", {}).get("id")) if x["properties"].get("backendAddressPool") else "",
     "redirectConfigurationName": last_seg(x["properties"].get("redirectConfiguration", {}).get("id")) if x["properties"].get("redirectConfiguration") else ""}
    for x in p.get("requestRoutingRules", [])]

live = {
    "frontendPorts": frontendPorts,
    "backendAddressPools": backendAddressPools,
    "httpListeners": httpListeners,
    "requestRoutingRules": requestRoutingRules,
    # add probes, urlPathMaps, redirectConfigurations, sslCerts similarly
}

# --- 3. Compare against current prd block (CHECK mode) ---
with open(FILE) as f:
    data = json.load(f)

prd = data["environmentDetails"]["prd"]

def unwrap(v):  # handle {"value":[...]} wrapper
    return v["value"] if isinstance(v, dict) and "value" in v else v

print("=== DIFFERENCE CHECK (prod config vs live) ===\n")
for key, live_val in live.items():
    cur = unwrap(prd.get(key, []))
    live_names = {i.get("name") for i in live_val}
    cur_names = {i.get("name") for i in cur}
    added = live_names - cur_names
    removed = cur_names - live_names
    if added: print(f"[{key}] LIVE has, config missing: {added}")
    if removed: print(f"[{key}] config has, LIVE missing: {removed}")
    if not added and not removed: print(f"[{key}] names match ({len(live_names)} items)")

# --- 4. Write updated file for review (does NOT overwrite original) ---
new = copy.deepcopy(data)
for key, live_val in live.items():
    if isinstance(new["environmentDetails"]["prd"].get(key), dict) and "value" in new["environmentDetails"]["prd"][key]:
        new["environmentDetails"]["prd"][key]["value"] = live_val
    else:
        new["environmentDetails"]["prd"][key] = live_val

with open("environmentDefaults.updated.json", "w") as f:
    json.dump(new, f, indent=2)

print("\nWritten environmentDefaults.updated.json (review before using).")
print("Run: diff environmentDefaults.json environmentDefaults.updated.json")
