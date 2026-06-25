import json, copy

LIVE = "live_prod.json"          # from step 1
FILE = "environmentDefaults.json"

with open(LIVE) as f:
    gw = json.load(f)
p = gw.get("properties", gw)

def last_seg(rid):
    return rid.rstrip("/").split("/")[-1] if rid else None

frontendPorts = sorted(
    [{"name": x["name"], "port": x["properties"]["port"]} for x in p.get("frontendPorts", [])],
    key=lambda r: r["port"])

httpListeners = [
    {"name": x["name"],
     "frontendPortName": last_seg(x["properties"].get("frontendPort", {}).get("id")),
     "protocol": x["properties"].get("protocol"),
     "hostName": x["properties"].get("hostName", ""),
     "sslCertificateName": last_seg(x["properties"].get("sslCertificate", {}).get("id")) if x["properties"].get("sslCertificate") else "",
     "requireServerNameIndication": x["properties"].get("requireServerNameIndication", False)}
    for x in p.get("httpListeners", [])]

backendAddressPools = [
    {"name": x["name"], "backendAddresses": x["properties"].get("backendAddresses", [])}
    for x in p.get("backendAddressPools", [])]

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
    "httpListeners": httpListeners,
    "backendAddressPools": backendAddressPools,
    "requestRoutingRules": requestRoutingRules,
}

with open(FILE) as f:
    data = json.load(f)
prd = data["environmentDetails"]["prd"]

def unwrap(v):
    return v["value"] if isinstance(v, dict) and "value" in v else v

print("=== CHECK: prod config vs live ===\n")
for key, lv in live.items():
    cur = unwrap(prd.get(key, []))
    lnames = {i.get("name") for i in lv}
    cnames = {i.get("name") for i in cur}
    if lnames - cnames: print(f"[{key}] LIVE has, config MISSING: {lnames - cnames}")
    if cnames - lnames: print(f"[{key}] config has, LIVE missing: {cnames - lnames}")
    if lnames == cnames: print(f"[{key}] match ({len(lnames)})")

new = copy.deepcopy(data)
for key, lv in live.items():
    t = new["environmentDetails"]["prd"]
    if isinstance(t.get(key), dict) and "value" in t[key]:
        t[key]["value"] = lv
    else:
        t[key] = lv

with open("environmentDefaults.updated.json", "w") as f:
    json.dump(new, f, indent=2)

print("\nWritten environmentDefaults.updated.json — review with diff.")
