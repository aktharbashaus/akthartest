#!/usr/bin/env python3
"""
generate_variables.py
---------------------
Run this in VS Code terminal:

    python generate_variables.py

Reads  AppGateway_ARM_Full.json  from the same folder
Writes variables.json  in proper ARM parameters format

Requirements: Python 3.6+  (no pip installs needed)
"""

import json
import sys
import os

INPUT_FILE  = "AppGateway_ARM_Full.json"
OUTPUT_FILE = "variables.json"

# ── Load ARM template ─────────────────────────────────────────
print(f"Reading {INPUT_FILE} ...")
if not os.path.exists(INPUT_FILE):
    print(f"ERROR: {INPUT_FILE} not found in current folder.")
    sys.exit(1)

with open(INPUT_FILE, encoding="utf-8") as f:
    arm = json.load(f)

props = arm["resources"][0]["
properties"]

# ── Helper ────────────────────────────────────────────────────
def id_name(id_str, segment):
    marker = f"/{segment}/"
    if marker in id_str:
        return id_str.split(marker)[-1].rstrip("')]")
    return ""

# ── 1. Backend Pools ──────────────────────────────────────────
print("Processing backend pools ...")
backend_pools = []
for p in props["backendAddressPools"]:
    backend_pools.append({
        "name": p["name"],
        "backendAddresses": p["properties"].get("backendAddresses", [])
    })

# ── 2. HTTP Settings ──────────────────────────────────────────
print("Processing HTTP settings ...")
http_settings = []
for s in props["backendHttpSettingsCollection"]:
    p = s["properties"]
    probe_id   = p.get("probe", {}).get("id", "")
    probe_name = id_name(probe_id, "probes")
    entry = {
        "name":                           s["name"],
        "port":                           p["port"],
        "protocol":                       "Https",
        "hostName":                       p.get("hostName", ""),
        "requestTimeout":                 p.get("requestTimeout", 120),
        "pickHostNameFromBackendAddress": False,
        "cookieBasedAffinity":            "Disabled"
    }
    if probe_name:
        entry["probeName"] = probe_name
    http_settings.append(entry)

# ── 3. Probes ─────────────────────────────────────────────────
print("Processing probes ...")
probes = []
for probe in props["probes"]:
    p = probe["properties"]
    probes.append({
        "name":               probe["name"],
        "host":               p["host"],
        "path":               p["path"],
        "interval":           p["interval"],
        "timeout":            p["timeout"],
        "unhealthyThreshold": p.get("unhealthyThreshold", 3),
        "statusCodes":        p.get("match", {}).get("statusCodes", ["200-399"])
    })

# ── 4. Listeners ──────────────────────────────────────────────
print("Processing listeners ...")
listeners = []
for lst in props["httpListeners"]:
    p       = lst["properties"]
    fip_id  = p.get("frontendIPConfiguration", {}).get("id", "")
    port_id = p.get("frontendPort", {}).get("id", "")
    cert_id = p.get("sslCertificate", {}).get("id", "")
    listeners.append({
        "name":                         lst["name"],
        "frontendIPConfigurationName":  "appPublicFrontendIp" if "appPublicFrontendIp" in fip_id else "internal",
        "frontendPortName":             id_name(port_id, "frontendPorts"),
        "protocol":                     p.get("protocol", "Https"),
        "sslCertificateName":           id_name(cert_id, "sslCertificates"),
        "hostName":                     p.get("hostName", ""),
        "requireServerNameIndication":  p.get("requireServerNameIndication", False),
        "attachWafPolicy":              bool(p.get("firewallPolicy", {}).get("id"))
    })

# ── 5. URL Path Maps ──────────────────────────────────────────
print("Processing URL path maps ...")
url_path_maps = []
for upm in props["urlPathMaps"]:
    p = upm["properties"]
    path_rules = []
    for pr in p.get("pathRules", []):
        pr_p = pr["properties"]
        path_rules.append({
            "name":                   pr["name"],
            "paths":                  pr_p.get("paths", []),
            "backendAddressPoolName": id_name(pr_p.get("backendAddressPool",  {}).get("id", ""), "backendAddressPools"),
            "backendHttpSettingsName": id_name(pr_p.get("backendHttpSettings", {}).get("id", ""), "backendHttpSettingsCollection")
        })
    url_path_maps.append({
        "name":                           upm["name"],
        "defaultBackendAddressPoolName":  id_name(p.get("defaultBackendAddressPool",  {}).get("id", ""), "backendAddressPools"),
        "defaultBackendHttpSettingsName": id_name(p.get("defaultBackendHttpSettings", {}).get("id", ""), "backendHttpSettingsCollection"),
        "pathRules":                      path_rules
    })

# ── 6. Routing Rules ──────────────────────────────────────────
print("Processing routing rules ...")
routing_rules = []
seen_priorities = {}
for rule in props["requestRoutingRules"]:
    p        = rule["properties"]
    priority = p.get("priority", 0)
    entry = {
        "name":             rule["name"],
        "ruleType":         p.get("ruleType", "Basic"),
        "priority":         priority,
        "httpListenerName": id_name(p.get("httpListener", {}).get("id", ""), "httpListeners")
    }
    if p.get("ruleType") == "PathBasedRouting":
        entry["urlPathMapName"] = id_name(p.get("urlPathMap", {}).get("id", ""), "urlPathMaps")
    else:
        entry["backendAddressPoolName"]  = id_name(p.get("backendAddressPool",  {}).get("id", ""), "backendAddressPools")
        entry["backendHttpSettingsName"] = id_name(p.get("backendHttpSettings", {}).get("id", ""), "backendHttpSettingsCollection")
    if priority in seen_priorities:
        entry["_WARNING"] = f"Duplicate priority {priority} - also used by {seen_priorities[priority]} - fix before deploying"
    seen_priorities[priority] = rule["name"]
    routing_rules.append(entry)

# ── 7. Assemble parameter values ──────────────────────────────
print("Assembling parameters ...")

param_values = {
    "create":               True,
    "appGatewayName":       "ndhappsdev-ags",
    "managedIdentityName":  "ndhappsdev-ags-id",
    "publicIpName":         "ndhappsdev-ags-public-ip",
    "wafPolicyName":        "dev-detection",
    "skuName":              "WAF_v2",
    "tier":                 "WAF_v2",
    "internalIpAddress":    "10.242.62.25",
    "keyVaultName":         "odh-ssl-certs",
    "wildcardCertSecretName": "ODH-WildcardCert",
    "sslPolicyName":        "AppGwSslPolicy20170401S",
    "autoscaleMinCapacity": 0,
    "autoscaleMaxCapacity": 10,
    "tags":                 {"agency": "odh"},

    "sslCerts": [
        {"name": "odh-wildcardcert11132020", "keyVaultSecretName": "ODH-WildcardCert"},
        {"name": "onh-complaint",            "keyVaultSecretName": "TODO-verify-from-portal"},
        {"name": "odh-cert",                 "keyVaultSecretName": "TODO-verify-from-portal"}
    ],

    "wafConfiguration": {
        "enabled":                True,
        "firewallMode":           "Detection",
        "ruleSetType":            "OWASP",
        "ruleSetVersion":         "3.0",
        "requestBodyCheck":       True,
        "maxRequestBodySizeInKb": 128,
        "fileUploadLimitInMb":    100,
        "exclusions": [
            {"matchVariable": "RequestCookieName", "selectorMatchOperator": "Equals",     "selector": "oidc-state"},
            {"matchVariable": "RequestArgName",    "selectorMatchOperator": "Equals",     "selector": "state"},
            {"matchVariable": "RequestArgName",    "selectorMatchOperator": "StartsWith", "selector": "Controls"},
            {"matchVariable": "RequestCookieName", "selectorMatchOperator": "StartsWith", "selector": "OpenIdConnect"},
            {"matchVariable": "RequestCookieName", "selectorMatchOperator": "Equals",     "selector": "AspNet.Cookie"}
        ]
    },

    "redirectConfigurations": [
        {"name": "smokecomplaint-DevRule",
         "redirectType": "Permanent",
         "targetUrl": "https://workplacesmoking-dev.odh.ohio.gov/ComplaintReport/Createreport",
         "includePath": True, "includeQueryString": True,
         "linkedRoutingRuleName": "smokecomplaint-DevRule"},
        {"name": "smokecomplaint-DevRule-https",
         "redirectType": "Permanent",
         "targetUrl": "https://workplacesmoking-dev.odh.ohio.gov/ComplaintReport/Createreport",
         "includePath": True, "includeQueryString": True,
         "linkedRoutingRuleName": "smokecomplaint-DevRule-https"},
        {"name": "Https-APIN-TstRule",
         "redirectType": "Permanent",
         "targetUrl": "TODO-verify-from-portal",
         "includePath": True, "includeQueryString": True}
    ],

    "backendAddressPools":           backend_pools,
    "backendHttpSettingsCollection": http_settings,
    "probes":                        probes,
    "httpListeners":                 listeners,
    "urlPathMaps":                   url_path_maps,
    "requestRoutingRules":           routing_rules
}

# ── 8. Wrap in ARM parameters schema ─────────────────────────
# This is REQUIRED - without $schema the pipeline fails with
# "Unable to deserialize response data"
output = {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        key: {"value": val} for key, val in param_values.items()
    }
}

# ── 9. Write output ───────────────────────────────────────────
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

# ── Summary ───────────────────────────────────────────────────
size_kb = os.path.getsize(OUTPUT_FILE) // 1024
lines   = open(OUTPUT_FILE).read().count('\n')

print()
print("=" * 55)
print(f"  SUCCESS: {OUTPUT_FILE} generated")
print("=" * 55)
print(f"  Schema               : ARM parameters format")
print(f"  Backend pools        : {len(backend_pools)}")
print(f"  HTTP settings        : {len(http_settings)}")
print(f"  Probes               : {len(probes)}")
print(f"  Listeners            : {len(listeners)}")
print(f"  Routing rules        : {len(routing_rules)}")
print(f"  URL path maps        : {len(url_path_maps)}")
print(f"  File size            : ~{size_kb} KB  ({lines} lines)")
print()

dups = [r for r in routing_rules if "_WARNING" in r]
if dups:
    print(f"  WARNING: {len(dups)} duplicate routing rule priorities:")
    for d in dups:
        print(f"    - {d['name']} priority {d['priority']}")
    print("  Fix these in variables.json before deploying!")
    print()

print("  Deploy command:")
print("  az deployment group create \\")
print("    --resource-group ndhapps-dev-shared-rg \\")
print("    --template-file main.bicep \\")
print("    --parameters @variables.json \\")
print("    --mode Incremental")
