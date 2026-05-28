// ============================================================
// appGateway.bicep  –  Reusable App Gateway module
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
      name: skuName
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
    // any() used to bypass type checker for optional probe property
    backendHttpSettingsCollection: [for s in backendHttpSettingsCollection: {
      name: s.name
      properties: {
        port: s.port
        protocol: 'Https'
        cookieBasedAffinity: 'Disabled'
        hostName: s.hostName
        pickHostNameFromBackendAddress: false
        requestTimeout: s.requestTimeout
        connectionDraining: {
          enabled: false
          drainTimeoutInSec: 1
        }
        probe: contains(s, 'probeName') ? any({
          id: '${agwId}/probes/${s.probeName}'
        }) : null
      }
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
    // any() used to bypass type checker for optional firewallPolicy and sslCertificate
    httpListeners: [for lst in httpListeners: {
      name: lst.name
      properties: {
        firewallPolicy: lst.attachWafPolicy ? any({
          id: wafPolicy.id
        }) : null
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
        sslCertificate: !empty(lst.sslCertificateName) ? any({
          id: '${agwId}/sslCertificates/${lst.sslCertificateName}'
        }) : null
        requireServerNameIndication: lst.requireServerNameIndication
      }
    }]

    // ── URL Path Maps ────────────────────────────────────────
    // Note: nested for loop (pathRules inside urlPathMaps) — valid in Bicep 0.4+
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
    // any() used for optional backendAddressPool, backendHttpSettings, urlPathMap
    requestRoutingRules: [for rule in requestRoutingRules: {
      name: rule.name
      properties: {
        ruleType: rule.ruleType
        priority: rule.priority
        httpListener: {
          id: '${agwId}/httpListeners/${rule.httpListenerName}'
        }
        backendAddressPool: rule.ruleType == 'Basic' ? any({
          id: '${agwId}/backendAddressPools/${rule.backendAddressPoolName}'
        }) : null
        backendHttpSettings: rule.ruleType == 'Basic' ? any({
          id: '${agwId}/backendHttpSettingsCollection/${rule.backendHttpSettingsName}'
        }) : null
        urlPathMap: rule.ruleType == 'PathBasedRouting' ? any({
          id: '${agwId}/urlPathMaps/${rule.urlPathMapName}'
        }) : null
      }
    }]

    // ── Redirect Configurations ──────────────────────────────
    redirectConfigurations: [for rc in redirectConfigurations: {
      name: rc.name
      properties: {
        redirectType: rc.redirectType
        targetUrl: rc.targetUrl
        includePath: contains(rc, 'includePath') ? rc.includePath : false
        includeQueryString: contains(rc, 'includeQueryString') ? rc.includeQueryString : false
        requestRoutingRules: contains(rc, 'linkedRoutingRuleName') ? any([
          { id: '${agwId}/requestRoutingRules/${rc.linkedRoutingRuleName}' }
        ]) : null
      }
    }]

    // ── WAF Configuration ────────────────────────────────────
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
