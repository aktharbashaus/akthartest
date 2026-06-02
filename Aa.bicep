// Add these existing resources in keyVault.bicep
resource callerPrincipalApp 'Microsoft.Web/sites@2022-09-01' existing = 
  [for (permission, i) in permissions: 
    if (empty(permission.principalSlotName) && 
        !empty(permission.principalResourceName)) {
  name: permission.principalResourceName
  scope: resourceGroup(permission.principalResourceGroup 
    ?? resourceGroup().name)
}]

resource callerPrincipalSlot 'Microsoft.Web/sites/slots@2022-09-01' existing = 
  [for (permission, i) in permissions: 
    if (!empty(permission.principalSlotName) && 
        !empty(permission.principalResourceName)) {
  name: '${permission.principalResourceName}/${permission.principalSlotName}'
  scope: resourceGroup(permission.principalResourceGroup 
    ?? resourceGroup().name)
}]

// Then in keyVaultRbacAccessModule pass resolved principalId
module keyVaultRbacAccessModule './keyVaultRbacAccess.bicep' = 
  [for (projectPermission, i) in permissions: 
    if (enableRbacAuthorization) {
  name: 'keyVaultRbacAccess-${i}-...'
  params: {
    // existing params
    managedIdentityPrincipalId: !empty(projectPermission.objectId)
      ? projectPermission.objectId  // Group/SP with known objectId ✅
      : !empty(projectPermission.principalSlotName)
        ? callerPrincipalSlot[i].identity.principalId  // slot ✅
        : callerPrincipalApp[i].identity.principalId   // app ✅
  }
}]
