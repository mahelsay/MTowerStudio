<#
.SYNOPSIS
  Grant MTower Studio data-plane roles. Run by the subscription OWNER (you), not the SPN.

.DESCRIPTION
  Contributor (the SPN) cannot grant roles, so the Owner runs this after Deploy-Studio.ps1 -Apply.
  Grants the studio SPN (and, if resolvable, you) the data roles needed to call models and read/write storage:
    Cognitive Services User · Azure AI User · Storage Blob Data Contributor.
  Re-run after a tenant move (role assignments are wiped when a subscription changes tenant).

.EXAMPLE
  ./Grant-StudioAccess.ps1            # dry run (What-If)
  ./Grant-StudioAccess.ps1 -Apply     # grant for real (opens an interactive Owner sign-in)
#>
[CmdletBinding()]
param(
  [switch]$Apply,
  [string]$UserObjectId  # optional: your AAD object id, to also grant yourself (portal/playground use)
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $here '..\..')
$access = Join-Path $here '..\bicep\access.bicep'

# --- Read config from .env (IDs only; no secret needed here) ---
$envVars = @{}
Get-Content (Join-Path $repoRoot '.env') | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
  $k, $v = $_ -split '=', 2; $envVars[$k.Trim()] = $v.Trim()
}
$sub    = $envVars['AZURE_SUBSCRIPTION_ID']
$client = $envVars['AZURE_CLIENT_ID']
$rg     = $envVars['AZURE_RESOURCE_GROUP']
$foundry = 'me-eus2-mtowerstudio-fdy'
$storage = 'meeus2mtowerstudiost01'
$mediaFoundry = 'me-swc-mtowerstudio-fdy'   # second-region media Foundry (gpt-image-2, sora-2)

# --- Interactive Owner sign-in ---
Write-Host "Sign in as the subscription Owner (a browser window will open)..." -ForegroundColor Cyan
Connect-AzAccount -Tenant $envVars['AZURE_TENANT_ID'] -Subscription $sub | Out-Null

# --- Resolve the SPN's object id from its app (client) id ---
$sp = Get-AzADServicePrincipal -ApplicationId $client
if (-not $sp) { throw "Could not resolve the studio SPN (app id $client)." }
$principals = @(@{ id = $sp.Id; type = 'ServicePrincipal' })
if ($UserObjectId) { $principals += @{ id = $UserObjectId; type = 'User' } }
Write-Host "Granting roles to: $($principals.id -join ', ')" -ForegroundColor Cyan

$deployName = "mtowerstudio-access-$(Get-Date -Format yyyyMMdd-HHmmss)"
$p = @{ foundryName = $foundry; storageAccountName = $storage; mediaFoundryName = $mediaFoundry; principals = $principals }

if ($Apply) {
  New-AzResourceGroupDeployment -ResourceGroupName $rg -Name $deployName -TemplateFile $access -TemplateParameterObject $p
  Write-Host "Roles granted. They can take up to ~10 minutes to apply. Then run Test-Studio.ps1." -ForegroundColor Green
} else {
  New-AzResourceGroupDeployment -ResourceGroupName $rg -Name $deployName -TemplateFile $access -TemplateParameterObject $p -WhatIf
  Write-Host "`nDry run only. Re-run with -Apply to grant." -ForegroundColor Yellow
}
