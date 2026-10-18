// MTower Studio — Azure landing zone entry point (subscription scope).
// Creates (reconciles) the resource group, then the studio (Foundry + models + storage + NSP + diagnostics) and the budget.
// Names follow docs/04-azure-landing-zone.md: me-<region>-mtowerstudio-<type>, lowercase.
// Independent of the legacy MTower resource group (me-eus2-mtower-studio-rg); this is the new studio's own home.
targetScope = 'subscription'

@description('Constant owner prefix of every resource name.')
param owner string = 'me'

@description('Region code used in names.')
param regionCode string = 'eus2'

@description('Azure region. East US 2 is the one US region that hosts gpt-image, sora-2, FLUX and the gpt-5.6 family together.')
param location string = 'eastus2'

@description('Workload token shared by all resources (no dash — distinct from legacy mtower-studio).')
param workload string = 'mtowerstudio'

@description('Public IPv4 addresses allowed through the firewalls (the studio PC). Single addresses only.')
param allowedIps array

@description('Resource ID of an existing Log Analytics workspace for diagnostics. Empty = no diagnostics.')
param logAnalyticsWorkspaceId string = ''

@description('Model deployments: name, format, model, version, sku, capacity.')
param modelDeployments array

@description('Monthly budget in USD for the studio resource group. Alerts only; never stops spending.')
param budgetAmount int = 700

@description('Who receives budget alerts.')
param budgetEmails array

@description('First day of the budget period (yyyy-MM-01). Fixed: a budget start date cannot be moved later.')
param budgetStartDate string

@description('Tags applied to every resource.')
param tags object = {
  workload: 'mtowerstudio'
  owner: 'me'
  managedBy: 'bicep'
  repo: 'mahelsay/MTowerStudio'
}

var baseName = '${owner}-${regionCode}-${workload}'
// Storage names: lowercase letters/digits only, max 24. '01' suffix avoids a global clash with the legacy studio storage.
var storageName = toLower(replace('${owner}${regionCode}${workload}st01', '-', ''))

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: '${baseName}-rg'
  location: location
  tags: tags
}

module studio 'modules/studio.bicep' = {
  scope: rg
  name: '${baseName}-studio'
  params: {
    location: location
    baseName: baseName
    storageName: storageName
    allowedIps: allowedIps
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    modelDeployments: modelDeployments
    tags: tags
  }
}

module budget 'modules/budget.bicep' = {
  scope: rg
  name: '${baseName}-budget'
  params: {
    name: '${baseName}-budget'
    amount: budgetAmount
    contactEmails: budgetEmails
    startDate: budgetStartDate
  }
}

@description('Second-region media Foundry (same RG): region, region code, and its deployments. Empty deployments = none.')
param mediaLocation string = 'swedencentral'
param mediaRegionCode string = 'swc'
param mediaDeployments array = []

module media 'modules/media.bicep' = if (!empty(mediaDeployments)) {
  scope: rg
  name: '${owner}-${mediaRegionCode}-${workload}-media'
  params: {
    location: mediaLocation
    name: '${owner}-${mediaRegionCode}-${workload}-fdy'
    allowedIps: allowedIps
    modelDeployments: mediaDeployments
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    tags: tags
  }
}

output resourceGroupName string = rg.name
output foundryName string = studio.outputs.foundryName
output foundryEndpoint string = studio.outputs.foundryEndpoint
output projectName string = studio.outputs.projectName
output projectEndpoint string = studio.outputs.projectEndpoint
output storageAccountName string = studio.outputs.storageAccountName
output blobEndpoint string = studio.outputs.blobEndpoint
output deploymentNames array = studio.outputs.deploymentNames
output mediaEndpoint string = !empty(mediaDeployments) ? 'https://${owner}-${mediaRegionCode}-${workload}-fdy.cognitiveservices.azure.com' : ''
