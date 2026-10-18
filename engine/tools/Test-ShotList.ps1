<#
.SYNOPSIS
  Validates production shot lists against the studio library, casting, and look blocks.

.DESCRIPTION
  Checks: JSON parses; shot IDs unique; every character ID is cast in casting.json;
  every LOC/VEH/PRP/WRD ID exists in the studio library; every look and lens key exists
  in looks.json (or as a production alias); dialogue_refs point to real shots;
  shot durations per beat vs. beat target. Prints a summary per beat and per file.

.EXAMPLE
  ./Test-ShotList.ps1 -ShotList ../../../productions/thunderbolt/ep01_romani/02_preproduction/shot_list_01_act_one.json
#>
param(
  [Parameter(Mandatory)] [string[]] $ShotList,
  [int] $TolerancePercent = 15
)

$ErrorActionPreference = 'Stop'
$studio = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$lib = Join-Path $studio 'library'
function Load($p) { Get-Content -Raw -Encoding utf8 $p | ConvertFrom-Json }

$looks = Load (Join-Path $lib 'looks\looks.json')
$ids = @{}
foreach ($cat in 'locations', 'vehicles', 'props', 'wardrobe') {
  (Load (Join-Path $lib "$cat\$cat.json")).$cat | ForEach-Object { $ids[$_.id] = $true }
}
$lensKeys = @{}; $looks.camera.PSObject.Properties.Name | ForEach-Object { $lensKeys[$_] = $true }

$exit = 0
foreach ($file in $ShotList) {
  $path = Resolve-Path $file
  $dir = Split-Path $path
  $issues = New-Object System.Collections.Generic.List[string]
  try { $sl = Load $path } catch { Write-Host "FAIL $file - invalid JSON: $($_.Exception.Message)" -ForegroundColor Red; $exit = 1; continue }

  $config = Load (Join-Path $dir $sl.production_config)
  $casting = Load (Join-Path $dir $sl.casting)
  $lookKeys = @{}; $looks.look.PSObject.Properties.Name | ForEach-Object { $lookKeys[$_] = $true }
  $config.look_aliases.PSObject.Properties.Name | ForEach-Object { $lookKeys[$_] = $true }
  $cast = @{}; $casting.cast.PSObject.Properties.Name | ForEach-Object { $cast[$_] = $true }

  $seen = @{}; $total = 0; $shots = 0; $premium = 0; $lips = 0
  Write-Host "`n== $(Split-Path $path -Leaf) ==" -ForegroundColor Cyan
  foreach ($b in $sl.beats) {
    $sum = 0
    foreach ($s in $b.shots) {
      $shots++; $sum += [double]$s.duration_s
      if ($seen.ContainsKey($s.shot_id)) { $issues.Add("duplicate shot_id $($s.shot_id)") }; $seen[$s.shot_id] = $true
      $chars = @(); if ($s.characters) { $chars = @($s.characters | ForEach-Object { if ($_ -is [string]) { $_ } else { $_.id } }) }
      foreach ($c in $chars) { if (-not $cast.ContainsKey($c)) { $issues.Add("$($s.shot_id): character $c not in casting.json") } }
      $assetText = (@($s.assets) + @($s.location) + @($b.location)) -join ' '
      foreach ($m in [regex]::Matches($assetText, '(LOC|VEH|PRP|WRD)-\d{4}')) { if (-not $ids.ContainsKey($m.Value)) { $issues.Add("$($s.shot_id): unknown library ID $($m.Value)") } }
      $lookList = if ($s.look) { $s.look } elseif ($b.look) { $b.look } else { @() }
      foreach ($l in $lookList) { if (-not $lookKeys.ContainsKey($l)) { $issues.Add("$($s.shot_id): unknown look $l") } }
      if ($s.lens -and -not $lensKeys.ContainsKey($s.lens)) { $issues.Add("$($s.shot_id): unknown lens $($s.lens)") }
      $model = if ($s.model) { $s.model } elseif ($s.video_model) { $s.video_model } else { 'default' }
      if ($model -eq 'premium') { $premium++ }
      if ($s.lip_sync -eq 'required') { $lips++ }
    }
    foreach ($d in @($b.dialogue_refs)) { if ($d -and $d.shot_id -and -not (@($b.shots.shot_id) -contains $d.shot_id)) { $issues.Add("beat $($b.beat): dialogue ref to missing shot $($d.shot_id)") } }
    $target = if ($b.target_s) { $b.target_s } else { $b.target_length_s }
    $flag = if ($target -and [math]::Abs($sum - $target) -gt ($target * $TolerancePercent / 100)) { '  <-- check length' } else { '' }
    Write-Host ("  {0,-5} {1,3} shots  {2,4}s / target {3,4}s{4}" -f $b.beat, @($b.shots).Count, $sum, $target, $flag)
    $total += $sum
  }
  Write-Host ("  TOTAL {0} shots | {1}s ({2:N1} min) | premium {3} | lip-sync required {4}" -f $shots, $total, ($total / 60), $premium, $lips)
  if ($issues.Count) { $exit = 1; $issues | ForEach-Object { Write-Host "  x $_" -ForegroundColor Yellow } } else { Write-Host "  OK - no issues" -ForegroundColor Green }
}
exit $exit
