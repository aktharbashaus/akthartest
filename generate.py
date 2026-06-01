#!/usr/bin/env python3
"""
generate_variables_from_azure.py
---------------------------------
Pulls live config from Azure and generates variables.json

Usage:
    python generate_variables_from_azure.py

Requirements:
    - Azure CLI installed and logged in (az login)
    - Python 3.6+
"""

import json
import subprocess
import sys
import os

# ── Update these two lines for your environment ───────────────
GATEWAY_NAME   = "odhappsdev-agw"
RESOURCE_GROUP = "odhapps-dev-shared-rg"
KEY_VAULT_NAME = "odh-ssl-certs"
OUTPUT_FILE    = "variables.json"
# ─────────────────────────────────────────────────────────────

def az(cmd):
    result = subprocess.run(f"az {cmd} --output json",
                            shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()}")
        return None
    return json.loads(result.stdout) if result.stdout.strip() else None

def id_name(id_str, segment):
    marker = f"/{segment}/"
    if id_str and marker in id_str:
        return id_str.split(marker)[-1].rstrip("')]")
    return ""

# ── Pull live gateway ─────────────────────────────────────────
print(f"Pulling live config for {GATEWAY_NAME} ...")
agw = az(f"network application-gateway show "
         f"--name {GATEWAY_NAME} "
         f"--resource-group {RESOURCE_GROUP}")

if not agw:
    print("ERROR: Could not reach gateway. Run 'az login' first.")
    sys.exit(1)

props = agw.get("properties", agw)

# ── Extract resource names ────────────────────────────────────
pub_ip_id    = ""
internal_ip  = "10.242.62.25"
for fip in props.get("frontendIPConfigurations", []):
    fp = fip.get("properties", {})
    if fp.get("publicIPAddress"):
        pub_ip_id = fp["publicIPAddress"].get("id", "")
    if fp.get("privateIPAllocationMethod") == "Static":
        internal_ip = fp.get("privateIPAddress", internal_ip)

pub_ip_name   = id_name(pub_ip_id, "publicIPAddresses") or "TODO-verify-publicip"
identity_ids  = agw.get("identity", {}).get("userAssignedIdentities", {})
identity_name = id_name(list(identity_ids.keys())[0], "userAssignedIdentities") if identity_ids else "TODO-verify-identity"
waf_policy_id = props.get("firewallPolicy", {}).get("id", "")
waf_policy_name = id_name(waf_policy_id, "applicationGatewayWebApplicationFirewallPolicies") or "dev-detection"
sku           = agw.get("sku", props.get("sku", {}))
autoscale     = props.get("autoscaleConfiguration", {})
ssl_policy    = props.get("sslPolicy", {})

# ── SSL Certs ─────────────────────────────────────────────────
ssl_certs = []
for cert in props.get("sslCertificates", []):
    cp = cert.get("properties", {})
    ssl_certs.append({
        "name": cert["name"],
        "keyVaultSecretName": id_name(cp.get("keyVaultSecretId", ""), "secrets")
                              or f"TODO-verify-{cert['name']}"
    })

# ── WAF Config ────────────────────────────────────────────────
waf_raw = props.get("webApplicationFirewallConfiguration", {})
waf_config = {
    "enabled":                waf_raw.get("enabled", True),
    "firewallMode":           waf_raw.get("firewallMode", "Detection"),
    "ruleSetType":            waf_raw.get("ruleSetType", "OWASP"),
    "ruleSetVersion":         waf_raw.get("ruleSetVersion", "3.0"),
    "requestBodyCheck":       waf_raw.get("requestBodyCheck", True),
    "maxRequestBodySizeInKb": waf_raw.get("maxRequestBodySizeInKb", 128),
    "fileUploadLimitInMb":    waf_raw.get("fileUploadLimitInMb", 100),
    "exclusions": [
        {
            "matchVariable":         e.get("matchVariable"),
            "selectorMatchOperator": e.get("selectorMatchOperator"),
            "selector":              e.get("selector")
        }
        for e in waf_raw.get("exclusions", [])
    ]
}

# ── Backend Pools ─────────────────────────────────────────────
backend_pools = []
for p in props.get("backendAddressPools", []):
    backend_pools.append({
        "name": p["name"],
        "backendAddresses": p.get("properties", {}).get("backendAddresses", [])
    })

# ── HTTP Settings ─────────────────────────────────────────────
http_settings = []
for s in props.get("backendHttpSettingsCollection", []):
    sp = s.get("properties", {})
    entry = {
        "name":                           s["name"],
        "port":                           sp.get("port", 443),
        "protocol":                       sp.get("protocol", "Https"),
        "hostName":                       sp.get("hostName", ""),
        "requestTimeout":                 sp.get("requestTimeout", 120),
        "pickHostNameFromBackendAddress": False,
        "cookieBasedAffinity":            sp.get("cookieBasedAffinity", "Disabled")
    }
    probe_name = id_name(sp.get("probe", {}).get("id", ""), "probes")
    if probe_name:
        entry["probeName"] = probe_name
    http_settings.append(entry)

# ── Probes ────────────────────────────────────────────────────
probes = []
for probe in props.get("probes", []):
    pp = probe.get("properties", {})
    probes.append({
        "name":               probe["name"],
        "host":               pp.get("host", ""),
        "path":               pp.get("path", "/"),
        "interval":           pp.get("interval", 30),
        "timeout":            pp.get("timeout", 30),
        "unhealthyThreshold": pp.get("unhealthyThreshold", 3),
        "statusCodes":        pp.get("match", {}).get("statusCodes", ["200-399"])
    })

# ── Listeners ─────────────────────────────────────────────────
listeners = []
for lst in props.get("httpListeners", []):
    lp = lst.get("properties", {})
    listeners.append({
        "name":                        lst["name"],
        "frontendIPConfigurationName": "appPublicFrontendIp" if "appPublicFrontendIp" in lp.get("frontendIPConfiguration", {}).get("id", "") else "internal",
        "frontendPortName":            id_name(lp.get("frontendPort", {}).get("id", ""), "frontendPorts"),
        "protocol":                    lp.get("protocol", "Https"),
        "sslCertificateName":          id_name(lp.get("sslCertificate", {}).get("id", ""), "sslCertificates"),
        "hostName":                    lp.get("hostName", ""),
        "requireServerNameIndication": lp.get("requireServerNameIndication", False),
        "attachWafPolicy":             bool(lp.get("firewallPolicy", {}).get("id"))
    })

# ── URL Path Maps ─────────────────────────────────────────────
url_path_maps = []
for upm in props.get("urlPathMaps", []):
    up = upm.get("properties", {})
    url_path_maps.append({
        "name":                           upm["name"],
        "defaultBackendAddressPoolName":  id_name(up.get("defaultBackendAddressPool",  {}).get("id", ""), "backendAddressPools"),
        "defaultBackendHttpSettingsName": id_name(up.get("defaultBackendHttpSettings", {}).get("id", ""), "backendHttpSettingsCollection"),
        "pathRules": [
            {
                "name":                    pr["name"],
                "paths":                   pr.get("properties", {}).get("paths", []),
                "backendAddressPoolName":  id_name(pr.get("properties", {}).get("backendAddressPool",  {}).get("id", ""), "backendAddressPools"),
                "backendHttpSettingsName": id_name(pr.get("properties", {}).get("backendHttpSettings", {}).get("id", ""), "backendHttpSettingsCollection")
            }
            for pr in up.get("pathRules", [])
        ]
    })

# ── Routing Rules ─────────────────────────────────────────────
routing_rules = []
seen_priorities = {}
for rule in props.get("requestRoutingRules", []):
    rp       = rule.get("properties", {})
    priority = rp.get("priority", 0)
    entry = {
        "name":             rule["name"],
        "ruleType":         rp.get("ruleType", "Basic"),
        "priority":         priority,
        "httpListenerName": id_name(rp.get("httpListener", {}).get("id", ""), "httpListeners")
    }
    if rp.get("ruleType") == "PathBasedRouting":
        entry["urlPathMapName"] = id_name(rp.get("urlPathMap", {}).get("id", ""), "urlPathMaps")
    elif rp.get("redirectConfiguration", {}).get("id"):
        entry["redirectConfigurationName"] = id_name(rp["redirectConfiguration"]["id"], "redirectConfigurations")
    else:
        entry["backendAddressPoolName"]  = id_name(rp.get("backendAddressPool",  {}).get("id", ""), "backendAddressPools")
        entry["backendHttpSettingsName"] = id_name(rp.get("backendHttpSettings", {}).get("id", ""), "backendHttpSettingsCollection")
    if priority in seen_priorities:
        entry["_WARNING"] = f"Duplicate priority {priority} - fix before deploying"
    seen_priorities[priority] = rule["name"]
    routing_rules.append(entry)

# ── Redirect Configs ──────────────────────────────────────────
redirect_configs = []
for rc in props.get("redirectConfigurations", []):
    rcp = rc.get("properties", {})
    entry = {
        "name":         rc["name"],
        "redirectType": rcp.get("redirectType", "Permanent"),
        "targetUrl":    rcp.get("targetUrl", "TODO-verify")
    }
    if rcp.get("includePath"):      entry["includePath"]      = True
    if rcp.get("includeQueryString"): entry["includeQueryString"] = True
    linked = rcp.get("requestRoutingRules", [])
    if linked:
        entry["linkedRoutingRuleName"] = id_name(linked[0].get("id", ""), "requestRoutingRules")
    redirect_configs.append(entry)

# ── Write variables.json ──────────────────────────────────────
output = {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        key: {"value": val} for key, val in {
            "create":               True,
            "appGatewayName":       GATEWAY_NAME,
            "managedIdentityName":  identity_name,
            "publicIpName":         pub_ip_name,
            "wafPolicyName":        waf_policy_name,
            "skuName":              sku.get("name", "WAF_v2"),
            "tier":                 sku.get("tier", "WAF_v2"),
            "internalIpAddress":    internal_ip,
            "keyVaultName":         KEY_VAULT_NAME,
            "wildcardCertSecretName": "ODH-WildcardCert",
            "sslPolicyName":        ssl_policy.get("policyName", "AppGwSslPolicy20170401S"),
            "autoscaleMinCapacity": autoscale.get("minCapacity", 0),
            "autoscaleMaxCapacity": autoscale.get("maxCapacity", 10),
            "tags":                 agw.get("tags", {"agency": "odh"}),
            "sslCerts":             ssl_certs,
            "wafConfiguration":     waf_config,
            "redirectConfigurations":        redirect_configs,
            "backendAddressPools":           backend_pools,
            "backendHttpSettingsCollection": http_settings,
            "probes":                        probes,
            "httpListeners":                 listeners,
            "urlPathMaps":                   url_path_maps,
            "requestRoutingRules":           routing_rules
        }.items()
    }
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

# ── Summary ───────────────────────────────────────────────────
size_kb = os.path.getsize(OUTPUT_FILE) // 1024
print(f"\n{'='*50}")
print(f"  SUCCESS: {OUTPUT_FILE} generated")
print(f"{'='*50}")
print(f"  Pools       : {len(backend_pools)}")
print(f"  Settings    : {len(http_settings)}")
print(f"  Probes      : {len(probes)}")
print(f"  Listeners   : {len(listeners)}")
print(f"  Rules       : {len(routing_rules)}")
print(f"  Redirects   : {len(redirect_configs)}")
print(f"  Size        : ~{size_kb} KB")
dups = [r for r in routing_rules if "_WARNING" in r]
if dups:
    print(f"\n  WARNING: {len(dups)} duplicate priorities - fix before deploying")
