<#
.SYNOPSIS
  Deploy (or dry-run) the MTower Studio Azure landing zone.

.DESCRIPTION
  Signs in as the studio SPN (from the repo-root .env), re-detects the studio PC's public IP, and runs the
  landing-zone Bicep at subscription scope. Dry run (What-If) by default; pass -Apply to deploy.

  Data-plane roles are NOT granted here (Contributor cannot grant roles) — the Owner runs Grant-StudioAccess.ps1.

.EXAMPLE
  ./Deploy-Studio.ps1            # dry run (What-If): shows what would change, changes nothing
  ./Deploy-Studio.ps1 -Apply     # deploy for real (after you review the What-If)
#>
[CmdletBinding()]
param(
  [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $here '..\..')
$bicep = Join-Path $here '..\bicep\main.bicep'
$params = Join-Path $here '..\bicep\main.bicepparam'

# --- Load .env (repo root) ---
$envFile = Join-Path $repoRoot '.env'
if (-not (Test-Path $envFile)) { throw ".env not found at $envFile" }
$envVars = @{}
Get-Content $envFile | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
  $k, $v = $_ -split '=', 2
  $envVars[$k.Trim()] = $v.Trim()
}
$tenant = $envVars['AZURE_TENANT_ID']
$sub    = $envVars['AZURE_SUBSCRIPTION_ID']
$client = $envVars['AZURE_CLIENT_ID']
$secret = $envVars['AZURE_CLIENT_SECRET']
if (-not ($tenant -and $sub -and $client -and $secret)) { throw 'Azure SPN values missing from .env' }

# --- Sign in as the SPN ---
Write-Host "Signing in as the studio SPN..." -ForegroundColor Cyan
$cred = New-Object System.Management.Automation.PSCredential($client, (ConvertTo-SecureString $secret -AsPlainText -Force))
Connect-AzAccount -ServicePrincipal -Credential $cred -Tenant $tenant -Subscription $sub | Out-Null
$ctx = Get-AzContext
Write-Host "  Subscription: $($ctx.Subscription.Name)" -ForegroundColor DarkGray

# --- Detect the studio PC public IP ---
$ip = (Invoke-RestMethod 'https://api.ipify.org?format=json').ip
Write-Host "Studio PC public IP: $ip" -ForegroundColor Cyan
$baked = (Get-Content $params | Select-String "'(\d+\.\d+\.\d+\.\d+)'").Matches.Groups[1].Value
if ($baked -and $baked -ne $ip) {
  Write-Warning "Detected IP ($ip) differs from the IP in main.bicepparam ($baked). Update main.bicepparam's allowedIps before applying, or the firewall will lock out this PC."
}

# --- Register required providers (idempotent) ---
foreach ($ns in 'Microsoft.CognitiveServices','Microsoft.Storage','Microsoft.Network','Microsoft.Insights','Microsoft.Consumption') {
  $state = (Get-AzResourceProvider -ProviderNamespace $ns -ErrorAction SilentlyContinue).RegistrationState | Select-Object -First 1
  if ($state -ne 'Registered') { Write-Host "  registering $ns..." -ForegroundColor DarkGray; Register-AzResourceProvider -ProviderNamespace $ns | Out-Null }
}

$deployName = "mtowerstudio-lz-$(Get-Date -Format yyyyMMdd-HHmmss)"
$common = @{
  Name                  = $deployName
  Location              = 'eastus2'
  TemplateFile          = $bicep
  TemplateParameterFile = $params
}

if ($Apply) {
  Write-Host "`nDEPLOYING (New-AzSubscriptionDeployment)..." -ForegroundColor Green
  $r = New-AzSubscriptionDeployment @common
  Write-Host "Provisioning state: $($r.ProvisioningState)" -ForegroundColor Green
  $r.Outputs.GetEnumerator() | ForEach-Object { Write-Host ("  {0} = {1}" -f $_.Key, $_.Value.Value) }
  Write-Host "`nNext: the Owner runs Grant-StudioAccess.ps1 to grant data roles, then Test-Studio.ps1." -ForegroundColor Yellow
} else {
  Write-Host "`nDRY RUN (What-If) — nothing will change:`n" -ForegroundColor Yellow
  New-AzSubscriptionDeployment @common -WhatIf
  Write-Host "`nReview the above, then re-run with -Apply to deploy." -ForegroundColor Yellow
}
