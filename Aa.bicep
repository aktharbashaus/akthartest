var allPathRules = [for upm in urlPathMaps: [for pr in upm.pathRules: {
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
}]]
