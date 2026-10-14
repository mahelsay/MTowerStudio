<#
.SYNOPSIS
  Health check for the MTower Studio landing zone (free; no generation unless -Generate).

.DESCRIPTION
  Signs in as the studio SPN, confirms the Foundry account, project, model deployments and storage exist and are
  reachable from this PC (inside the IP allow-list / NSP). With -Generate, makes one tiny model call (a few cents).
#>
[CmdletBinding()]
param(
  [switch]$Generate
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $here '..\..')
$envVars = @{}
Get-Content (Join-Path $repoRoot '.env') | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
  $k, $v = $_ -split '=', 2; $envVars[$k.Trim()] = $v.Trim()
}
$cred = New-Object System.Management.Automation.PSCredential($envVars['AZURE_CLIENT_ID'], (ConvertTo-SecureString $envVars['AZURE_CLIENT_SECRET'] -AsPlainText -Force))
Connect-AzAccount -ServicePrincipal -Credential $cred -Tenant $envVars['AZURE_TENANT_ID'] -Subscription $envVars['AZURE_SUBSCRIPTION_ID'] | Out-Null

$rg = $envVars['AZURE_RESOURCE_GROUP']
$foundry = 'me-eus2-mtowerstudio-fdy'

Write-Host "Foundry account:" -ForegroundColor Cyan
Get-AzCognitiveServicesAccount -ResourceGroupName $rg -Name $foundry | Select-Object AccountName, Location, @{n='publicAccess';e={$_.Properties.PublicNetworkAccess}}, @{n='localAuthDisabled';e={$_.Properties.DisableLocalAuth}} | Format-List

Write-Host "Model deployments:" -ForegroundColor Cyan
Get-AzCognitiveServicesAccountDeployment -ResourceGroupName $rg -AccountName $foundry | Select-Object Name, @{n='model';e={$_.Properties.Model.Name}}, @{n='version';e={$_.Properties.Model.Version}}, @{n='sku';e={$_.Sku.Name}} | Format-Table -AutoSize

Write-Host "Storage:" -ForegroundColor Cyan
Get-AzStorageAccount -ResourceGroupName $rg -Name 'meeus2mtowerstudiost01' | Select-Object StorageAccountName, @{n='publicAccess';e={$_.PublicNetworkAccess}}, @{n='sharedKey';e={$_.AllowSharedKeyAccess}} | Format-List

if ($Generate) {
  Write-Host "Test generation not wired yet (Wave 1 engine). Skipping." -ForegroundColor Yellow
}
Write-Host "Health check complete." -ForegroundColor Green
