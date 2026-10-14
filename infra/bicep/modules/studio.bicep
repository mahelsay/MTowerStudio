// MTower Studio — the studio itself (resource-group scope).
// Security baseline: Entra ID sign-in only (no keys), public endpoints locked to the studio PC's IP, NSP for the
// tenant SFI storage policy, diagnostics to Log Analytics. Deployments are pay-per-use (Global Standard): idle = $0.

param location string
param baseName string
param storageName string
param allowedIps array
param logAnalyticsWorkspaceId string
param modelDeployments array
param tags object

var diagnosticsEnabled = !empty(logAnalyticsWorkspaceId)

// ---------------------------------------------------------------- Foundry resource (AI Services) + project (agent fleet)

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: '${baseName}-fdy'
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
    customSubDomainName: '${baseName}-fdy'
    allowProjectManagement: true
    disableLocalAuth: true // Entra ID only: no API keys exist to leak
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: [for ip in allowedIps: { value: ip }]
      virtualNetworkRules: []
    }
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: baseName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: baseName
    description: 'MTower Studio — the multi-agent virtual studio fleet (orchestrator + specialist crew).'
  }
}

// One at a time: parallel writes to the same account conflict.
@batchSize(1)
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for d in modelDeployments: {
    parent: foundry
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
    dependsOn: [
      project
    ]
  }
]

// ---------------------------------------------------------------- Storage (threads, artifacts, generated media)

resource storage 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // Entra ID only
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'SecuredByPerimeter' // the NSP decides (tenant SFI policy disables plain public access)
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      ipRules: [for ip in allowedIps: { value: ip, action: 'Allow' }]
      virtualNetworkRules: []
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
  }
}

resource mediaContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: 'media'
  properties: {
    publicAccess: 'None'
  }
}

// ---------------------------------------------------------------- Network Security Perimeter
// Tenant policy "SFI-NS2.2.1 Secure PaaS Resources" (MCAPSGov) forces storage public access off unless in an NSP.
// Enforced: only the inbound rule (the studio PC) gets in; NSP rules take precedence over each resource's own setting.

resource perimeter 'Microsoft.Network/networkSecurityPerimeters@2025-09-01' = {
  name: '${baseName}-nsp'
  location: location
  tags: tags
  properties: {}
}

resource perimeterProfile 'Microsoft.Network/networkSecurityPerimeters/profiles@2025-09-01' = {
  parent: perimeter
  name: '${baseName}-nsp-profile'
  location: location
  properties: {}
}

resource allowStudioPc 'Microsoft.Network/networkSecurityPerimeters/profiles/accessRules@2025-09-01' = {
  parent: perimeterProfile
  name: '${baseName}-allow-pc'
  location: location
  properties: {
    direction: 'Inbound'
    addressPrefixes: [for ip in allowedIps: '${ip}/32']
  }
}

resource foundryAssociation 'Microsoft.Network/networkSecurityPerimeters/resourceAssociations@2025-09-01' = {
  parent: perimeter
  name: '${baseName}-fdy-nspa'
  location: location
  properties: {
    privateLinkResource: {
      id: foundry.id
    }
    profile: {
      id: perimeterProfile.id
    }
    accessMode: 'Enforced'
  }
  dependsOn: [
    deployments
    allowStudioPc
  ]
}

resource storageAssociation 'Microsoft.Network/networkSecurityPerimeters/resourceAssociations@2025-09-01' = {
  parent: perimeter
  name: '${baseName}-st-nspa'
  location: location
  properties: {
    privateLinkResource: {
      id: storage.id
    }
    profile: {
      id: perimeterProfile.id
    }
    accessMode: 'Enforced'
  }
  dependsOn: [
    mediaContainer
    allowStudioPc
  ]
}

// ---------------------------------------------------------------- Diagnostics

resource perimeterDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (diagnosticsEnabled) {
  name: '${baseName}-nsp-diag'
  scope: perimeter
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
  }
}

resource foundryDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (diagnosticsEnabled) {
  name: '${baseName}-fdy-diag'
  scope: foundry
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

resource storageDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (diagnosticsEnabled) {
  name: '${baseName}-st-diag'
  scope: storage
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    metrics: [
      {
        category: 'Transaction'
        enabled: true
      }
    ]
  }
}

resource blobDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (diagnosticsEnabled) {
  name: '${baseName}-blob-diag'
  scope: blobService
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
        category: 'Transaction'
        enabled: true
      }
    ]
  }
}

output foundryName string = foundry.name
output foundryEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/'
output projectName string = project.name
output projectEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}'
output storageAccountName string = storage.name
output blobEndpoint string = storage.properties.primaryEndpoints.blob
output deploymentNames array = [for (d, i) in modelDeployments: deployments[i].name]
