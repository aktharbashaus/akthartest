// ============================================================
// appGateway.bicep  –  Reusable App Gateway module
// All configuration arrays come from variables.json via main.bicep
// ============================================================

// ── Parameters from variables.json ───────────────────────────
param create bool = true
param appGatewayName string
param skuName string = 'WAF_v2'
param tier string = 'WAF_v2'
param internalIpAddress string
param managedIdentityName string
param publicIpName string
param wafPolicyName string
param keyVaultName string
param wildcardCertSecretName string
param sslCerts array
param wafConfiguration object
param sslPolicyName string = 'AppGwSslPolicy20170401S'
param autoscaleMinCapacity int = 0
param autoscaleMaxCapacity int = 10
param tags object = {}
param redirectConfigurations array = []

// ── The big arrays (all from variables.json) ─────────────────
param backendAddressPools array
param backendHttpSettingsCollection array
param probes array
param httpListeners array
param urlPathMaps array
param requestRoutingRules array

// ── Parameters from environmentDefaults.json ─────────────────
param location string = 'eastus'
param vnetName string
param vnetResourceGroup string
param subnetName string
param sharedResourceGroup string

// ── Existing resource references ─────────────────────────────
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
  scope: resourceGroup(sharedResourceGroup)
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2023-06-01' existing = {
  name: publicIpName
  scope: resourceGroup(sharedResourceGroup)
}

resource wafPolicy 'Microsoft.Network/applicationGatewayWebApplicationFirewallPolicies@2023-06-01' existing = {
  name: wafPolicyName
  scope: resourceGroup(sharedResourceGroup)
}

// ── Derived variables ─────────────────────────────────────────
var subnetId = resourceId(vnetResourceGroup, 'Microsoft.Network/virtualNetworks/subnets', vnetName, subnetName)
var internalFrontendIpName = '${appGatewayName}-internalip'
var agwId = resourceId('Microsoft.Network/applicationGateways', appGatewayName)
var kvBase = 'https://${keyVaultName}.vault.azure.net/secrets'

// ============================================================
// RESOURCE
// ============================================================
resource appGateway 'Microsoft.Network/applicationGateways@2023-06-01' = if (create) {
  name: appGatewayName
  location: location
  tags: tags
  zones: ['1', '2', '3']
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    sku: {
      name: skuName   // FIX 1: removed invalid 'family' property
      tier: tier
    }

    autoscaleConfiguration: {
      minCapacity: autoscaleMinCapacity
      maxCapacity: autoscaleMaxCapacity
    }

    sslPolicy: {
      policyType: 'Predefined'
      policyName: sslPolicyName
    }

    enableHttp2: false

    // ── Gateway IP ───────────────────────────────────────────
    gatewayIPConfigurations: [
      {
        name: 'appGatewayIpConfig'
        properties: {
          subnet: {
            id: subnetId
          }
        }
      }
    ]

    // ── SSL Certificates ─────────────────────────────────────
    sslCertificates: [for cert in sslCerts: {
      name: cert.name
      properties: {
        keyVaultSecretId: '${kvBase}/${cert.keyVaultSecretName}'
      }
    }]

    // ── Frontend IPs ─────────────────────────────────────────
    frontendIPConfigurations: [
      {
        name: 'appPublicFrontendIp'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: {
            id: publicIp.id
          }
        }
      }
      {
        name: internalFrontendIpName
        properties: {
          privateIPAddress: internalIpAddress
          privateIPAllocationMethod: 'Static'
          subnet: {
            id: subnetId
          }
        }
      }
    ]

    // ── Frontend Ports ───────────────────────────────────────
    frontendPorts: [
      {
        name: 'port_80'
        properties: {
          port: 80
        }
      }
      {
        name: 'port_443'
        properties: {
          port: 443
        }
      }
      {
        name: 'port_448'
        properties: {
          port: 448
        }
      }
    ]

    // ── Backend Pools ────────────────────────────────────────
    backendAddressPools: [for pool in backendAddressPools: {
      name: pool.name
      properties: {
        backendAddresses: pool.backendAddresses
      }
    }]

    // ── Backend HTTP Settings ────────────────────────────────
    // FIX 2: use union() to conditionally add probe — ARM rejects null values
    backendHttpSettingsCollection: [for s in backendHttpSettingsCollection: {
      name: s.name
      properties: union(
        {
          port: s.port
          protocol: 'Https'
          cookieBasedAffinity: 'Disabled'
          hostName: s.hostName
          pickHostNameFromBackendAddress: false
          requestTimeout: s.requestTimeout
          connectionDraining: {            // FIX 3: was inline one-liner, needs newlines
            enabled: false
            drainTimeoutInSec: 1
          }
        },
        contains(s, 'probeName') ? {
          probe: {
            id: '${agwId}/probes/${s.probeName}'
          }
        } : {}                             // empty object = omit probe entirely
      )
    }]

    // ── Probes ───────────────────────────────────────────────
    probes: [for p in probes: {
      name: p.name
      properties: {
        protocol: 'Https'
        host: p.host
        path: p.path
        interval: p.interval
        timeout: p.timeout
        unhealthyThreshold: p.unhealthyThreshold
        pickHostNameFromBackendHttpSettings: false
        minServers: 0
        match: {
          statusCodes: p.statusCodes
        }
      }
    }]

    // ── HTTP Listeners ───────────────────────────────────────
    // FIX 4: use union() for optional firewallPolicy and sslCertificate
    httpListeners: [for lst in httpListeners: {
      name: lst.name
      properties: union(
        {
          frontendIPConfiguration: {
            id: lst.frontendIPConfigurationName == 'appPublicFrontendIp'
              ? '${agwId}/frontendIPConfigurations/appPublicFrontendIp'
              : '${agwId}/frontendIPConfigurations/${internalFrontendIpName}'
          }
          frontendPort: {
            id: '${agwId}/frontendPorts/${lst.frontendPortName}'
          }
          protocol: lst.protocol
          hostName: lst.hostName
          requireServerNameIndication: lst.requireServerNameIndication
        },
        lst.attachWafPolicy ? {
          firewallPolicy: {
            id: wafPolicy.id
          }
        } : {},
        !empty(lst.sslCertificateName) ? {
          sslCertificate: {
            id: '${agwId}/sslCertificates/${lst.sslCertificateName}'
          }
        } : {}
      )
    }]

    // ── URL Path Maps ────────────────────────────────────────
    urlPathMaps: [for upm in urlPathMaps: {
      name: upm.name
      properties: {
        defaultBackendAddressPool: {
          id: '${agwId}/backendAddressPools/${upm.defaultBackendAddressPoolName}'
        }
        defaultBackendHttpSettings: {
          id: '${agwId}/backendHttpSettingsCollection/${upm.defaultBackendHttpSettingsName}'
        }
        pathRules: [for pr in upm.pathRules: {
          name: pr.name
          properties: {
            paths: pr.paths
            backendAddressPool: {
              id: '${agwId}/backendAddressPools/${pr.backendAddressPoolName}'
            }
            backendHttpSettings: {
              id: '${agwId}/backendHttpSettingsCollection/${pr.backendHttpSettingsName}'
            }
          }
        }]
      }
    }]

    // ── Routing Rules ────────────────────────────────────────
    // FIX 5: use union() for optional pool/settings/urlPathMap — ARM rejects null
    requestRoutingRules: [for rule in requestRoutingRules: {
      name: rule.name
      properties: union(
        {
          ruleType: rule.ruleType
          priority: rule.priority
          httpListener: {
            id: '${agwId}/httpListeners/${rule.httpListenerName}'
          }
        },
        rule.ruleType == 'Basic' ? {
          backendAddressPool: {
            id: '${agwId}/backendAddressPools/${rule.backendAddressPoolName}'
          }
          backendHttpSettings: {
            id: '${agwId}/backendHttpSettingsCollection/${rule.backendHttpSettingsName}'
          }
        } : {},
        rule.ruleType == 'PathBasedRouting' ? {
          urlPathMap: {
            id: '${agwId}/urlPathMaps/${rule.urlPathMapName}'
          }
        } : {}
      )
    }]

    // ── Redirect Configurations ──────────────────────────────
    redirectConfigurations: [for rc in redirectConfigurations: {
      name: rc.name
      properties: union(
        {
          redirectType: rc.redirectType
          targetUrl: rc.targetUrl
        },
        contains(rc, 'includePath') ? { includePath: rc.includePath } : {},
        contains(rc, 'includeQueryString') ? { includeQueryString: rc.includeQueryString } : {},
        contains(rc, 'linkedRoutingRuleName') ? {
          requestRoutingRules: [
            { id: '${agwId}/requestRoutingRules/${rc.linkedRoutingRuleName}' }
          ]
        } : {}
      )
    }]

    // ── WAF / Rewrite / Private Link ─────────────────────────
    rewriteRuleSets: []
    privateLinkConfigurations: []

    webApplicationFirewallConfiguration: {
      enabled: wafConfiguration.enabled
      firewallMode: wafConfiguration.firewallMode
      ruleSetType: wafConfiguration.ruleSetType
      ruleSetVersion: wafConfiguration.ruleSetVersion
      disabledRuleGroups: []
      exclusions: wafConfiguration.exclusions
      requestBodyCheck: wafConfiguration.requestBodyCheck
      maxRequestBodySizeInKb: wafConfiguration.maxRequestBodySizeInKb
      fileUploadLimitInMb: wafConfiguration.fileUploadLimitInMb
    }
  }
}

// ── Outputs ───────────────────────────────────────────────────
output appGatewayId string   = create ? appGateway.id : ''
output appGatewayName string = appGatewayName
