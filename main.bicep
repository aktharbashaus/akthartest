// ============================================================
// main.bicep  –  Entry point for App Gateway deployment
// Parameters sourced from:
//   variables.json           (app-specific config + all arrays)
//   environmentDefaults.json (env-wide networking config)
// ============================================================

// ── From variables.json ───────────────────────────────────────
param create bool = true
param appGatewayName string = 'ndhappsdev-ags'
param skuName string = 'WAF_v2'
param tier string = 'WAF_v2'
param internalIpAddress string = '10.242.62.25'
param managedIdentityName string = 'ndhappsdev-ags-id'
param publicIpName string = 'ndhappsdev-ags-public-ip'
param wafPolicyName string = 'dev-detection'
param keyVaultName string = 'odh-ssl-certs'
param wildcardCertSecretName string = 'ODH-WildcardCert'
param sslCerts array
param wafConfiguration object
param sslPolicyName string = 'AppGwSslPolicy20170401S'
param autoscaleMinCapacity int = 0
param autoscaleMaxCapacity int = 10
param tags object = { agency: 'odh' }
param redirectConfigurations array = []
param backendAddressPools array
param backendHttpSettingsCollection array
param probes array
param httpListeners array
param urlPathMaps array
param requestRoutingRules array

// ── From environmentDefaults.json ────────────────────────────
param location string = 'eastus'
param vnetName string = 'PrimaryVNet1'
param vnetResourceGroup string = 'Network101'
param subnetName string = 'ODH_AGS_AppGateway_Dev_Subnet'
param sharedResourceGroup string = 'ndhapps-dev-shared-rg'

// ── Module call ───────────────────────────────────────────────
module appGatewayModule './appGateway.bicep' = {
  name: 'deploy-${appGatewayName}'
  params: {
    create:                          create
    appGatewayName:                  appGatewayName
    skuName:                         skuName
    tier:                            tier
    internalIpAddress:               internalIpAddress
    managedIdentityName:             managedIdentityName
    publicIpName:                    publicIpName
    wafPolicyName:                   wafPolicyName
    keyVaultName:                    keyVaultName
    wildcardCertSecretName:          wildcardCertSecretName
    sslCerts:                        sslCerts
    wafConfiguration:                wafConfiguration
    sslPolicyName:                   sslPolicyName
    autoscaleMinCapacity:            autoscaleMinCapacity
    autoscaleMaxCapacity:            autoscaleMaxCapacity
    tags:                            tags
    redirectConfigurations:          redirectConfigurations
    backendAddressPools:             backendAddressPools
    backendHttpSettingsCollection:   backendHttpSettingsCollection
    probes:                          probes
    httpListeners:                   httpListeners
    urlPathMaps:                     urlPathMaps
    requestRoutingRules:             requestRoutingRules
    location:                        location
    vnetName:                        vnetName
    vnetResourceGroup:               vnetResourceGroup
    subnetName:                      subnetName
    sharedResourceGroup:             sharedResourceGroup
  }
}

// ── Outputs ───────────────────────────────────────────────────
output appGatewayId   string = appGatewayModule.outputs.appGatewayId
output appGatewayName string = appGatewayModule.outputs.appGatewayName
