// ============================================================
// main.bicep  -  Entry point for App Gateway deployment
// Follows ODH pattern:
//   variables.json          -> app-specific config + all arrays
//   environmentDefaults.json -> env-wide networking config
//                              read via loadJsonContent (same
//                              pattern as other ODH templates)
// ============================================================

// ── Environment selector (ODH pattern) ───────────────────────
@description('Target environment')
@allowed(['dev', 'tst', 'stg', 'prd', 'trn'])
param environment string

// ── Read environmentDefaults.json (ODH pattern) ──────────────
var environmentDetails = loadJsonContent('../../Variables/environmentDefaults.json').environmentDetails
var agwConfig   = environmentDetails[environment].appGateway
var vnetConfig  = environmentDetails[environment].vnet
var envLocation = environmentDetails[environment].location
var envSharedRG = environmentDetails[environment].sharedResourceGroup

// ── Parameters from variables.json ───────────────────────────
// App-specific config - same across all environments
param create bool

param skuName string
param tier string
param keyVaultName string
param wildcardCertSecretName string
param sslPolicyName string
param autoscaleMinCapacity int
param autoscaleMaxCapacity int
param tags object
param sslCerts array
param wafConfiguration object
param redirectConfigurations array = []

// ── Big arrays from variables.json ───────────────────────────
param backendAddressPools array
param backendHttpSettingsCollection array
param probes array
param httpListeners array
param urlPathMaps array
param requestRoutingRules array

// ── Module call ───────────────────────────────────────────────
module appGatewayModule './appGateway.bicep' = {
  name: 'deploy-${agwConfig.appGatewayName}'
  params: {
    // From environmentDefaults.json via loadJsonContent
    appGatewayName:      agwConfig.appGatewayName
    internalIpAddress:   agwConfig.internalIpAddress
    managedIdentityName: agwConfig.managedIdentityName
    publicIpName:        agwConfig.publicIpName
    wafPolicyName:       agwConfig.wafPolicyName
    subnetName:          agwConfig.subnetName
    vnetName:            vnetConfig.name
    vnetResourceGroup:   vnetConfig.resourceGroup
    location:            envLocation
    sharedResourceGroup: envSharedRG

    // From variables.json
    create:                          create
    skuName:                         skuName
    tier:                            tier
    keyVaultName:                    keyVaultName
    wildcardCertSecretName:          wildcardCertSecretName
    sslPolicyName:                   sslPolicyName
    autoscaleMinCapacity:            autoscaleMinCapacity
    autoscaleMaxCapacity:            autoscaleMaxCapacity
    tags:                            tags
    sslCerts:                        sslCerts
    wafConfiguration:                wafConfiguration
    redirectConfigurations:          redirectConfigurations
    backendAddressPools:             backendAddressPools
    backendHttpSettingsCollection:   backendHttpSettingsCollection
    probes:                          probes
    httpListeners:                   httpListeners
    urlPathMaps:                     urlPathMaps
    requestRoutingRules:             requestRoutingRules
  }
}

// ── Outputs ───────────────────────────────────────────────────
output appGatewayId   string = appGatewayModule.outputs.appGatewayId
output appGatewayName string = appGatewayModule.outputs.appGatewayName
