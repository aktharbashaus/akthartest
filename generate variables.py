#!/usr/bin/env python3
"""
generate_variables.py
---------------------
Run this in VS Code terminal on your office laptop:

    python generate_variables.py

It reads  AppGateway_ARM_Full.json  from the same folder
and writes variables.json  to the same folder.

Requirements: Python 3.6+  (no pip installs needed)
"""

import json
import sys
import os

# ── Config ────────────────────────────────────────────────────
INPUT_FILE  = "AppGateway_ARM_Full.json"   # your ARM export
OUTPUT_FILE = "variables.json"

# ── Load ARM template ─────────────────────────────────────────
print(f"Reading {INPUT_FILE} ...")
if not os.path.exists(INPUT_FILE):
    print(f"ERROR: {INPUT_FILE} not found in current folder.")
    print("       Make sure you run this script from the same folder as the ARM file.")
    sys.exit(1)

with open(INPUT_FILE, encoding="utf-8") as f:
    arm = json.load(f)

props = arm["resources"][0]["properties"]

# ── Helper: extract name from ARM resource ID ─────────────────
def id_name(id_str, segment):
    marker = f"/{segment}/"
    if marker in id_str:
        return id_str.split(marker)[-1].rstrip("')]")
    return ""

# ─────────────────────────────────────────────────────────────
# 1. BACKEND POOLS
# ─────────────────────────────────────────────────────────────
print("Processing backend pools ...")
backend_pools = []
for p in props["backendAddressPools"]:
    backend_pools.append({
        "name": p["name"],
        "backendAddresses": p["properties"].get("backendAddresses", [])
    })

# ─────────────────────────────────────────────────────────────
# 2. BACKEND HTTP SETTINGS
# ─────────────────────────────────────────────────────────────
print("Processing HTTP settings ...")
http_settings = []
for s in props["backendHttpSettingsCollection"]:
    p = s["properties"]
    probe_id = p.get("probe", {}).get("id", "")
    probe_name = id_name(probe_id, "probes")
    entry = {
        "name": s["name"],
        "port": p["port"],
        "protocol": "Https",
        "hostName": p.get("hostName", ""),
        "requestTimeout": p.get("requestTimeout", 120),
        "pickHostNameFromBackendAddress": False,
        "cookieBasedAffinity": "Disabled"
    }
    if probe_name:
        entry["probeName"] = probe_name
    http_settings.append(entry)

# ─────────────────────────────────────────────────────────────
# 3. PROBES
# ─────────────────────────────────────────────────────────────
print("Processing probes ...")
probes = []
for probe in props["probes"]:
    p = probe["properties"]
    probes.append({
        "name": probe["name"],
        "host": p["host"],
        "path": p["path"],
        "interval": p["interval"],
        "timeout": p["timeout"],
        "unhealthyThreshold": p.get("unhealthyThreshold", 3),
        "statusCodes": p.get("match", {}).get("statusCodes", ["200-399"])
    })

# ─────────────────────────────────────────────────────────────
# 4. HTTP LISTENERS
# ─────────────────────────────────────────────────────────────
print("Processing listeners ...")
listeners = []
for lst in props["httpListeners"]:
    p = lst["properties"]
    fip_id  = p.get("frontendIPConfiguration", {}).get("id", "")
    port_id = p.get("frontendPort", {}).get("id", "")
    cert_id = p.get("sslCertificate", {}).get("id", "")
    listeners.append({
        "name": lst["name"],
        "frontendIPConfigurationName": "appPublicFrontendIp" if "appPublicFrontendIp" in fip_id else "internal",
        "frontendPortName": id_name(port_id, "frontendPorts"),
        "protocol": p.get("protocol", "Https"),
        "sslCertificateName": id_name(cert_id, "sslCertificates"),
        "hostName": p.get("hostName", ""),
        "requireServerNameIndication": p.get("requireServerNameIndication", False),
        "attachWafPolicy": bool(p.get("firewallPolicy", {}).get("id"))
    })

# ─────────────────────────────────────────────────────────────
# 5. URL PATH MAPS
# ─────────────────────────────────────────────────────────────
print("Processing URL path maps ...")
url_path_maps = []
for upm in props["urlPathMaps"]:
    p = upm["properties"]
    path_rules = []
    for pr in p.get("pathRules", []):
        pr_p = pr["properties"]
        path_rules.append({
            "name": pr["name"],
            "paths": pr_p.get("paths", []),
            "backendAddressPoolName":    id_name(pr_p.get("backendAddressPool",    {}).get("id", ""), "backendAddressPools"),
            "backendHttpSettingsName":   id_name(pr_p.get("backendHttpSettings",   {}).get("id", ""), "backendHttpSettingsCollection")
        })
    url_path_maps.append({
        "name": upm["name"],
        "defaultBackendAddressPoolName":  id_name(p.get("defaultBackendAddressPool",  {}).get("id", ""), "backendAddressPools"),
        "defaultBackendHttpSettingsName": id_name(p.get("defaultBackendHttpSettings", {}).get("id", ""), "backendHttpSettingsCollection"),
        "pathRules": path_rules
    })

# ─────────────────────────────────────────────────────────────
# 6. ROUTING RULES
# ─────────────────────────────────────────────────────────────
print("Processing routing rules ...")
routing_rules = []
seen_priorities = {}
for rule in props["requestRoutingRules"]:
    p = rule["properties"]
    priority = p.get("priority", 0)
    entry = {
        "name": rule["name"],
        "ruleType": p.get("ruleType", "Basic"),
        "priority": priority,
        "httpListenerName": id_name(p.get("httpListener", {}).get("id", ""), "httpListeners")
    }
    if p.get("ruleType") == "PathBasedRouting":
        entry["urlPathMapName"] = id_name(p.get("urlPathMap", {}).get("id", ""), "urlPathMaps")
    else:
        entry["backendAddressPoolName"]  = id_name(p.get("backendAddressPool",  {}).get("id", ""), "backendAddressPools")
        entry["backendHttpSettingsName"] = id_name(p.get("backendHttpSettings", {}).get("id", ""), "backendHttpSettingsCollection")
    # Flag duplicate priorities
    if priority in seen_priorities:
        entry["_WARNING"] = f"Duplicate priority {priority} - also used by {seen_priorities[priority]} - fix before deploying"
    seen_priorities[priority] = rule["name"]
    routing_rules.append(entry)

# ─────────────────────────────────────────────────────────────
# 7. ASSEMBLE variables.json
# ─────────────────────────────────────────────────────────────
print("Assembling variables.json ...")

variables = {
    "_description": "App Gateway variables - generated from ARM export by generate_variables.py",
    "_deploy":  "az deployment group create --resource-group ndhapps-dev-shared-rg --template-file main.bicep --parameters @variables.json --mode Incremental",
    "_whatif":  "az deployment group what-if  --resource-group ndhapps-dev-shared-rg --template-file main.bicep --parameters @variables.json --mode Incremental",

    "create":               True,
    "appGatewayName":       "ndhappsdev-ags",
    "managedIdentityName":  "ndhappsdev-ags-id",
    "publicIpName":         "ndhappsdev-ags-public-ip",
    "wafPolicyName":        "dev-detection",
    "skuName":              "WAF_v2",
    "tier":                 "WAF_v2",
    "family":               "Generation_2",
    "internalIpAddress":    "10.242.62.25",
    "keyVaultName":         "odh-ssl-certs",
    "wildcardCertSecretName": "ODH-WildcardCert",
    "sslPolicyName":        "AppGwSslPolicy20170401S",
    "autoscaleMinCapacity": 0,
    "autoscaleMaxCapacity": 10,
    "tags":                 {"agency": "odh"},

    "sslCerts": [
        {
            "name": "odh-wildcardcert11132020",
            "keyVaultSecretName": "ODH-WildcardCert"
        },
        {
            "name": "onh-complaint",
            "keyVaultSecretName": "TODO-verify-from-portal"
        },
        {
            "name": "odh-cert",
            "keyVaultSecretName": "TODO-verify-from-portal"
        }
    ],

    "wafConfiguration": {
        "enabled":                 True,
        "firewallMode":            "Detection",
        "ruleSetType":             "OWASP",
        "ruleSetVersion":          "3.0",
        "requestBodyCheck":        True,
        "maxRequestBodySizeInKb":  128,
        "fileUploadLimitInMb":     100,
        "exclusions": [
            {"matchVariable": "RequestCookieName", "selectorMatchOperator": "Equals",     "selector": "oidc-state"},
            {"matchVariable": "RequestArgName",    "selectorMatchOperator": "Equals",     "selector": "state"},
            {"matchVariable": "RequestArgName",    "selectorMatchOperator": "StartsWith", "selector": "Controls"},
            {"matchVariable": "RequestCookieName", "selectorMatchOperator": "StartsWith", "selector": "OpenIdConnect"},
            {"matchVariable": "RequestCookieName", "selectorMatchOperator": "Equals",     "selector": "AspNet.Cookie"}
        ]
    },

    "redirectConfigurations": [
        {
            "name": "OnCircle-nth-route-redirectConfig",
            "redirectType": "Temporary",
            "targetUrl": "http://www.google.com",
            "includeQueryString": True,
            "_TODO": "verify exact name from portal"
        },
        {
            "name": "smokecomplaint-DevRule",
            "redirectType": "Permanent",
            "targetUrl": "https://workplacesmoking-dev.odh.ohio.gov/ComplaintReport/Createreport",
            "includePath": True,
            "includeQueryString": True,
            "linkedRoutingRuleName": "smokecomplaint-DevRule"
        },
        {
            "name": "smokecomplaint-DevRule-https",
            "redirectType": "Permanent",
            "targetUrl": "https://workplacesmoking-dev.odh.ohio.gov/ComplaintReport/Createreport",
            "includePath": True,
            "includeQueryString": True,
            "linkedRoutingRuleName": "smokecomplaint-DevRule-https"
        },
        {
            "name": "Https-APIN-TstRule",
            "redirectType": "Permanent",
            "targetUrl": "TODO-verify-from-portal",
            "includePath": True,
            "includeQueryString": True,
            "_TODO": "verify targetUrl from portal"
        }
    ],

    "backendAddressPools":           backend_pools,
    "backendHttpSettingsCollection": http_settings,
    "probes":                        probes,
    "httpListeners":                 listeners,
    "urlPathMaps":                   url_path_maps,
    "requestRoutingRules":           routing_rules
}

# ── Write output ──────────────────────────────────────────────
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(variables, f, indent=2)

# ── Summary ───────────────────────────────────────────────────
print()
print("=" * 50)
print(f"  SUCCESS: {OUTPUT_FILE} generated")
print("=" * 50)
print(f"  Backend pools    : {len(backend_pools)}")
print(f"  HTTP settings    : {len(http_settings)}")
print(f"  Probes           : {len(probes)}")
print(f"  Listeners        : {len(listeners)}")
print(f"  Routing rules    : {len(routing_rules)}")
print(f"  URL path maps    : {len(url_path_maps)}")
size_kb = os.path.getsize(OUTPUT_FILE) // 1024
print(f"  File size        : ~{size_kb} KB")
print()

# ── Warn about duplicates ─────────────────────────────────────
dups = [r for r in routing_rules if "_WARNING" in r]
if dups:
    print(f"  WARNING: {len(dups)} routing rules have duplicate priorities:")
    for d in dups:
        print(f"    - {d['name']} (priority {d['priority']}): {d['_WARNING']}")
    print()

print("  Next step: fix _WARNING priorities in variables.json")
print("             then run: az deployment group what-if ...")
