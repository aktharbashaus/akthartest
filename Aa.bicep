var allPathRules = map(urlPathMaps, upm => map(upm.pathRules, pr => {
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
}))
