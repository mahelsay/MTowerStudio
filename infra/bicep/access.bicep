// MTower Studio — data-plane permissions (resource-group scope).
// Run by the subscription OWNER (the user), NOT the SPN: Contributor cannot grant roles.
// Re-run after a tenant move: role assignments are deleted when a subscription changes tenant.
//
// Grants each principal:
//   Cognitive Services User       — call every model on the Foundry resource (reasoning + vision)
//   Azure AI User                 — use the Foundry project (agents, threads, portal playgrounds)
//   Storage Blob Data Contributor — read/write the media/threads container (shared keys are disabled)

param foundryName string
param storageAccountName string

@description('Second-region media Foundry (same RG). Empty = none.')
param mediaFoundryName string = ''

@description('Principals to grant: [{ id: <object id>, type: \'ServicePrincipal\' | \'User\' }]')
param principals array

var roles = {
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}

resource storage 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName
}

resource modelUsers 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for p in principals: {
    name: guid(foundry.id, p.id, roles.cognitiveServicesUser)
    scope: foundry
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesUser)
      principalId: p.id
      principalType: p.type
    }
  }
]

resource projectUsers 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for p in principals: {
    name: guid(foundry.id, p.id, roles.azureAiUser)
    scope: foundry
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.azureAiUser)
      principalId: p.id
      principalType: p.type
    }
  }
]

resource mediaWriters 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for p in principals: {
    name: guid(storage.id, p.id, roles.storageBlobDataContributor)
    scope: storage
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
      principalId: p.id
      principalType: p.type
    }
  }
]

resource mediaFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (!empty(mediaFoundryName)) {
  name: empty(mediaFoundryName) ? foundryName : mediaFoundryName
}

resource mediaModelUsers 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for p in (empty(mediaFoundryName) ? [] : principals): {
    name: guid(mediaFoundry.id, p.id, roles.cognitiveServicesUser)
    scope: mediaFoundry
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveServicesUser)
      principalId: p.id
      principalType: p.type
    }
  }
]
