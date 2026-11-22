# ISS26 DEV77 - audit all 54 Master League nationality-flag routes on known DEV75.
# Read-only. Never changes BIN, CUE, memory cards or update feeds.
param([string]$Archive="",[string]$Cue="",[switch]$NoPost)
$ErrorActionPreference="Stop"
$root="D:\ISS 26"
$diag=Join-Path $env:LOCALAPPDATA "ISS26\diagnostics\DEV77"
New-Item -ItemType Directory -Path $diag -Force | Out-Null
$script=Join-Path $diag "audit_ml_all_flags_dev77.py"
$url="https://raw.githubusercontent.com/Nevmerlyk/ISS26-Android/ce2728b99cb87acc2ef427fa30922b2d32a3afba/tools/ps1_graphics/audit_ml_all_flags_dev77.py"
Invoke-WebRequest -Uri $url -OutFile $script -UseBasicParsing
$python=Get-Command py.exe -ErrorAction SilentlyContinue
$arguments=@()
if($python){$arguments+=@("-3",$script)}
else {
 $python=Get-Command python.exe -ErrorAction SilentlyContinue
 if(-not $python){throw "Python 3 unavailable; no game files modified."}
 $arguments+=@($script)
}
if(-not $Cue){
 $known=Join-Path $root "ISS26_Data\experiments\DEV75-Flags-flag-styles\ISS26_DEV75_Flags_flag-styles.cue"
 if(Test-Path -LiteralPath $known){$Cue=$known}
 else {
  $dir=Join-Path $root "ISS26_Data\experiments"
  if(Test-Path -LiteralPath $dir){
   $hit=Get-ChildItem -LiteralPath $dir -Filter "*DEV75*.cue" -File -Recurse -ErrorAction SilentlyContinue|Select-Object -First 1
   if($hit){$Cue=$hit.FullName}
  }
 }
}
if(-not $Cue -or -not (Test-Path -LiteralPath $Cue -PathType Leaf)){
 throw "DEV75 CUE not found. Use the DEV76 verified launcher to install/check DEV75 first. No fallback to ordinary Test Game."
}
if(-not $Archive){
 $target="20261122_222725_df981b.zip"
 $try=@((Join-Path $env:USERPROFILE "Downloads\$target"),
        (Join-Path $root $target),
        (Join-Path $env:TEMP $target))
 foreach($p in $try){if(Test-Path -LiteralPath $p -PathType Leaf){$Archive=$p;break}}
 if(-not $Archive){
  foreach($directory in @((Join-Path $root "ISS26_Data\explorer"),
                           (Join-Path $root "ISS26_Data\reports"))){
   if(-not (Test-Path -LiteralPath $directory -PathType Container)){continue}
   $hit=Get-ChildItem -LiteralPath $directory -Filter $target -File -Recurse -ErrorAction SilentlyContinue|Select-Object -First 1
   if($hit){$Archive=$hit.FullName;break}
  }
 }
}
if(-not $Archive -or -not (Test-Path -LiteralPath $Archive -PathType Leaf)){
 throw "Latest DEV75 Academy report not found: 20261122_222725_df981b.zip. No other version substituted."
}
$arguments+=@("--cue",$Cue,"--archive",$Archive,"--out",$diag)
if(-not $NoPost -and (Get-Command gh.exe -ErrorAction SilentlyContinue)){$arguments+="--post-issue"}
Write-Host "ISS26 DEV77: validating EXACT DEV75 image; reading Academy archive."
& $python.Source @arguments
if($LASTEXITCODE -ne 0){throw "DEV77 validation failed (exit $LASTEXITCODE). Original image is unchanged."}
Write-Host "ISS26 DEV77 complete: 54-country table + screenshot-to-VRAM audit"
Write-Host ("Reports: " + $diag)
