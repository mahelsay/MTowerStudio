// MTower Studio — media Foundry (second region). Holds the generation models whose subscription quota in the main
// region is already in use (gpt-image-2, sora-2 in East US 2 belong to the legacy MTower Foundry). Same baseline as
// the main Foundry: Entra ID only (no keys), public endpoint locked to the studio PC, pay-per-use deployments.

param location string
param name string
param allowedIps array
param modelDeployments array
param logAnalyticsWorkspaceId string
param tags object

resource media 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: name
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: [for ip in allowedIps: { value: ip }]
      virtualNetworkRules: []
    }
  }
}

@batchSize(1)
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for d in modelDeployments: {
    parent: media
    name: d.name
    sku: {
      name: d.sku
      capacity: d.capacity
    }
    properties: {
      model: {
        format: d.format
        name: d.model
        version: d.version
      }
    }
  }
]

resource diag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: '${name}-diag'
  scope: media
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output name string = media.name
output endpoint string = 'https://${name}.cognitiveservices.azure.com'
output id string = media.id
