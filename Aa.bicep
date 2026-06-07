// Remove pathRulesForMap0/1/2 vars entirely
// Replace urlPathMaps with simple loop
urlPathMaps: [for upm in urlPathMaps: {
  name: upm.name
  properties: {
    defaultBackendAddressPool: {
      id: '${agwId}/backendAddressPools/${upm.defaultBackendAddressPoolName}'
    }
    defaultBackendHttpSettings: {
      id: '${agwId}/backendHttpSettingsCollection/${upm.defaultBackendHttpSettingsName}'
    }
    pathRules: upm.pathRules  // already has full ARM format from variables.json
  }
}]
