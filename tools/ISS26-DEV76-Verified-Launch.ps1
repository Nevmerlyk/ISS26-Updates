# ISS26 DEV76 verified single-image PCSX-Redux launcher.
# Windows PowerShell 5.1 compatible. Read-only; refuses wrong Track01.
param([string]$Cue = "", [string]$ReduxExe = "", [switch]$NoLaunch)
$ErrorActionPreference = "Stop"
$expected = "B89F848CCE7FB761EB7ED8A3F9BF26DC159E5248C185AC114BCF864555BAFD8E"
$original = "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
$alt = "C265019267C11DBBB60FA32E369FE5DA9E1759403D860E5F11824FD69AB0518C"
$dev74 = "8E5EEDCF2442AAA98894C3D38260D46A717CF36491A27B96A7A183E0ED2EBBA9"
$root = "D:\ISS 26"
$experimentRoot = Join-Path $root "ISS26_Data\experiments"
$diag = Join-Path $env:LOCALAPPDATA "ISS26\diagnostics"
New-Item -ItemType Directory -Path $diag -Force | Out-Null

function Read-CueBin([string]$cue) {
  $body = Get-Content -LiteralPath $cue -Raw -Encoding Default
  $entries = [regex]::Matches($body, '(?im)^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+BINARY')
  $tracks = [regex]::Matches($body,'(?im)^\s*TRACK\s+[0-9]+\s+')
  if($entries.Count -lt 1){throw "Invalid CUE, no BINARY FILE: $cue"}
  $file = if($entries[0].Groups[1].Success){$entries[0].Groups[1].Value}else{$entries[0].Groups[2].Value}
  if([IO.Path]::IsPathRooted($file)){$bin = $file}else{$bin=Join-Path (Split-Path -Parent $cue) $file}
  if(-not(Test-Path -LiteralPath $bin -PathType Leaf)){throw "Missing Track01: $bin"}
  if($tracks.Count -ne 12){throw "Expected all 12 tracks; found $($tracks.Count) in $cue"}
  return [pscustomobject]@{Cue=$cue;Bin=(Resolve-Path -LiteralPath $bin).Path;Tracks=$tracks.Count}
}
$candidates = New-Object System.Collections.Generic.List[string]
if($Cue) {
  if(-not(Test-Path -LiteralPath $Cue -PathType Leaf)){throw "Requested CUE does not exist: $Cue"}
  [void]$candidates.Add((Resolve-Path -LiteralPath $Cue).Path)
}else{
  $known = Join-Path $experimentRoot "DEV75-Flags-flag-styles\ISS26_DEV75_Flags_flag-styles.cue"
  if(Test-Path -LiteralPath $known -PathType Leaf){[void]$candidates.Add($known)}
  if(Test-Path -LiteralPath $experimentRoot){
    foreach($file in (Get-ChildItem -LiteralPath $experimentRoot -Filter "*.cue" -File -Recurse -ErrorAction SilentlyContinue)){
      if($file.Name -match "(?i)DEV75" -and -not $candidates.Contains($file.FullName)){
        [void]$candidates.Add($file.FullName)
      }
    }
  }
}
$seen = @{}
$checked = New-Object System.Collections.ArrayList
$selected = $null
foreach($candidate in $candidates) {
  try{
    $meta = Read-CueBin $candidate
    $hash = (Get-FileHash -LiteralPath $meta.Bin -Algorithm SHA256).Hash.ToUpperInvariant()
    $label = "OTHER"
    if($hash -eq $expected){$label="DEV75"}
    elseif($hash -eq $alt){$label="0.9.6-alt (ordinary Test)"}
    elseif($hash -eq $dev74){$label="DEV74"}
    elseif($hash -eq $original){$label="Original"}
    $obj = [ordered]@{Cue=$meta.Cue;BinName=[IO.Path]::GetFileName($meta.Bin);Tracks=$meta.Tracks;SHA256=$hash;IdentifiedAs=$label}
    [void]$checked.Add($obj)
    if($hash -eq $expected -and -not $selected){$selected=$meta}
    Write-Host "Found: $label | $($meta.Cue)"
  }catch{
    [void]$checked.Add([ordered]@{Cue=$candidate;Error=$_.Exception.Message})
    Write-Warning $_.Exception.Message
  }
}
$oldAudit = Join-Path $diag "DEV76-disc-runtime.json"
$audit = $null
if(Test-Path -LiteralPath $oldAudit -PathType Leaf){
  try{$audit=Get-Content -LiteralPath $oldAudit -Raw -Encoding UTF8 | ConvertFrom-Json}catch{}
}
$sourceCue = ""
if($audit -and $audit.academy -and $audit.academy.sessions){
  foreach($s in $audit.academy.sessions){
    foreach($field in $s.fields){
      if($field.name -eq ".cue"){$sourceCue=$field.value;break}
    }
    if($sourceCue){break}
  }
}
$report=[ordered]@{
  schema="ISS26_DEV76_VerifiedLaunch_v1"
  time_utc=[DateTime]::UtcNow.ToString("o")
  archive_session_cue=$sourceCue
  expected_DEV75_track01_sha256=$expected
  scanned=$checked
  verified_DEV75_cue=if($selected){$selected.Cue}else{$null}
  launched=$false
}
$out=Join-Path $diag "DEV76-verified-launch.json"
if(-not $selected) {
  $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $out -Encoding UTF8
  Write-Host "No exact DEV75 game image found. Your Academy session CUE was: $sourceCue"
  Write-Host "No emulator launched and no game files changed."
  Write-Host "If DEV75 is not installed, run Run-DEV75-Flags-Experimental.cmd from your existing DEV75 ZIP, then run this checker again."
  Write-Host "Report: $out"
  exit 2
}
Write-Host "VERIFIED DEV75: $($selected.Bin)"
Write-Host "SHA256: $expected"
if($NoLaunch) {
  $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $out -Encoding UTF8
  Write-Host "Verified CUE. No emulator started (-NoLaunch)."
  exit 0
}
if($ReduxExe -and -not (Test-Path -LiteralPath $ReduxExe -PathType Leaf)){throw "PCSX-Redux exe not found: $ReduxExe"}
if(-not $ReduxExe){
  $running=Get-Process -Name "pcsx-redux" -ErrorAction SilentlyContinue | Select-Object -First 1
  if($running -and $running.Path -and (Test-Path -LiteralPath $running.Path)){$ReduxExe=$running.Path}
}
if(-not $ReduxExe){
  $found=Get-Command pcsx-redux.exe -ErrorAction SilentlyContinue
  if($found){$ReduxExe=$found.Source}
}
if(-not $ReduxExe){
  $roots=@(
    (Join-Path $root "PCSX-Redux"),
    (Join-Path $root "ISS26_Data"),
    (Join-Path $env:LOCALAPPDATA "Programs\PCSX-Redux"),
    "C:\Program Files\PCSX-Redux"
  )
  foreach($dir in $roots){
    if(Test-Path -LiteralPath $dir -PathType Container){
      $exe=Get-ChildItem -LiteralPath $dir -Recurse -Filter pcsx-redux.exe -File -ErrorAction SilentlyContinue|Select-Object -First 1
      if($exe){$ReduxExe=$exe.FullName;break}
    }
  }
}
if(-not $ReduxExe){
  $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $out -Encoding UTF8
  Write-Host "DEV75 image verified, but PCSX-Redux executable not found automatically."
  Write-Host "Open this exact CUE in PCSX-Redux: $($selected.Cue)"
  exit 3
}
# -iso and -run are documented PCSX-Redux startup flags. Passing the
# exact pinned CUE ensures this new process cannot silently pick ordinary Test.
Start-Process -FilePath $ReduxExe -ArgumentList @("-iso",('"' + $selected.Cue + '"'),"-run") -WorkingDirectory (Split-Path -Parent $ReduxExe)
$report.launched=$true
$report.emulator_exe=[IO.Path]::GetFileName($ReduxExe)
$report.launch_arguments=@("-iso", $selected.Cue, "-run")
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $out -Encoding UTF8
Write-Host "Launched new PCSX-Redux process with VERIFIED DEV75 CUE; do not load old emulator save states."
Write-Host "Report: $out"
