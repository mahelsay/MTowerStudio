<#
.SYNOPSIS
  Launcher for the MTower production engine. Finds the real Python (not the Microsoft Store shortcut).

.EXAMPLE
  ./mtower.ps1 doctor
  ./mtower.ps1 prompt --shot 2.5-01
  ./mtower.ps1 generate anchors ACT-0003          # dry run: shows the plan and estimated cost
  ./mtower.ps1 review
#>
$ErrorActionPreference = 'Stop'
$candidates = @(
  "$env:LOCALAPPDATA\Python\bin\python.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
)
$python = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) {
  $python = (Get-Command python -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' } | Select-Object -First 1).Source
}
if (-not $python) { throw "Python 3.11+ not found. Install it from https://www.python.org/downloads/ and try again." }
$env:PYTHONPATH = $PSScriptRoot
$env:PYTHONUTF8 = '1'
& $python -m mtower @args
exit $LASTEXITCODE
