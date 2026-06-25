import json, copy

LIVE = "live_prod.json"              # from: az ... show > live_prod.json
FILE = "environmentDefaults.json"

# --- Load live prod (utf-8-sig handles the BOM) ---
with open(LIVE, encoding='utf-8-sig') as f:
    gw = json.load(f)
p = gw.get("properties", gw)

def last_seg(rid):
    return rid.rstrip("/").split("/")[-1] if rid else None

# --- Extract arrays (az output is FLAT - no "properties" wrapper) ---
frontendPorts = sorted(
    [{"name": x["name"], "port": x["port"]} for x in p.get("frontendPorts", [])],
    key=lambda r: r["port"])

httpListeners = [
    {"name": x["name"],
     "frontendPortName": last_seg(x.get("frontendPort", {}).get("id")),
     "protocol": x.get("protocol"),
     "hostName": x.get("hostName", ""),
     "sslCertificateName": last_seg(x.get("sslCertificate", {}).get("id")) if x.get("sslCertificate") else "",
     "requireServerNameIndication": x.get("requireServerNameIndication", False)}
    for x in p.get("httpListeners", [])]

backendAddressPools = [
    {"name": x["name"], "backendAddresses": x.get("backendAddresses", [])}
    for x in p.get("backendAddressPools", [])]

backendHttpSettingsCollection = [
    {"name": x["name"],
     "port": x.get("port"),
     "protocol": x.get("protocol"),
     "cookieBasedAffinity": x.get("cookieBasedAffinity"),
     "requestTimeout": x.get("requestTimeout"),
     "hostName": x.get("hostName", "")}
    for x in p.get("backendHttpSettingsCollection", [])]

probes = [
    {"name": x["name"],
     "protocol": x.get("protocol"),
     "host": x.get("host", ""),
     "path": x.get("path"),
     "interval": x.get("interval"),
     "timeout": x.get("timeout"),
     "unhealthyThreshold": x.get("unhealthyThreshold")}
    for x in p.get("probes", [])]

redirectConfigurations = [
    {"name": x["name"],
     "redirectType": x.get("redirectType"),
     "targetUrl": x.get("targetUrl", ""),
     "includePath": x.get("includePath", True),
     "includeQueryString": x.get("includeQueryString", True)}
    for x in p.get("redirectConfigurations", [])]

requestRoutingRules = [
    {"name": x["name"],
     "ruleType": x.get("ruleType"),
     "priority": x.get("priority"),
     "httpListenerName": last_seg(x.get("httpListener", {}).get("id")),
     "backendAddressPoolName": last_seg(x.get("backendAddressPool", {}).get("id")) if x.get("backendAddressPool") else "",
     "backendHttpSettingsName": last_seg(x.get("backendHttpSettings", {}).get("id")) if x.get("backendHttpSettings") else "",
     "redirectConfigurationName": last_seg(x.get("redirectConfiguration", {}).get("id")) if x.get("redirectConfiguration") else ""}
    for x in p.get("requestRoutingRules", [])]

live = {
    "frontendPorts": frontendPorts,
    "httpListeners": httpListeners,
    "backendAddressPools": backendAddressPools,
    "backendHttpSettingsCollection": backendHttpSettingsCollection,
    "probes": probes,
    "redirectConfigurations": redirectConfigurations,
    "requestRoutingRules": requestRoutingRules,
}

# --- Load your defaults ---
with open(FILE, encoding='utf-8-sig') as f:
    data = json.load(f)
prd = data["environmentDetails"]["prd"]

def unwrap(v):
    return v["value"] if isinstance(v, dict) and "value" in v else v

# --- CHECK: what differs between your prd config and live ---
print("=== DIFFERENCE CHECK (prd config vs live prod) ===\n")
for key, lv in live.items():
    cur = unwrap(prd.get(key, []))
    lnames = {i.get("name") for i in lv}
    cnames = {i.get("name") for i in cur}
    added = lnames - cnames
    removed = cnames - lnames
    if added:   print(f"[{key}] LIVE has, config MISSING: {sorted(added)}")
    if removed: print(f"[{key}] config has, LIVE missing: {sorted(removed)}")
    if not added and not removed: print(f"[{key}] names match ({len(lnames)} items)")

# --- Write updated file (preserves {"value":...} wrapper if present) ---
new = copy.deepcopy(data)
for key, lv in live.items():
    t = new["environmentDetails"]["prd"]
    if isinstance(t.get(key), dict) and "value" in t[key]:
        t[key]["value"] = lv
    else:
        t[key] = lv

with open("environmentDefaults.updated.json", "w", encoding="utf-8") as f:
    json.dump(new, f, indent=2)

print("\nWritten environmentDefaults.updated.json")
print("Review: diff environmentDefaults.json environmentDefaults.updated.json")
