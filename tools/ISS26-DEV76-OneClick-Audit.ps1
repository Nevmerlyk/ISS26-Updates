# ISS26 DEV76: read-only diagnostic with optional sanitized GitHub report.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File .\ISS26-DEV76-OneClick-Audit.ps1
param([string]$Cue="", [string]$Archive="", [switch]$NoPost)
$ErrorActionPreference="Stop"
$base=Join-Path $env:LOCALAPPDATA "ISS26\diagnostics"
New-Item -ItemType Directory -Force -Path $base | Out-Null
$py=Join-Path $base "ISS26_DEV76_DiscAndAcademyAudit.py"
$url="https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/fb7c5b2286550c66e640315b3cebafbf701ffe29/tools/ISS26_DEV76_DiscAndAcademyAudit.py"
Invoke-WebRequest -Uri $url -OutFile $py -UseBasicParsing
$python=$null
if(Get-Command py.exe -ErrorAction SilentlyContinue){$python="py.exe"}
elseif(Get-Command python.exe -ErrorAction SilentlyContinue){$python="python.exe"}
if(-not $python){throw "Python 3 is required (DEV76 never changes original BIN/CUE)."}
$args=@()
if($python -eq "py.exe"){$args+=@("-3")}
$args+=@($py)
if($Cue){$args+=@("--cue",$Cue)}
if($Archive){$args+=@("--zip",$Archive)}
else {
 $names=@(
  (Join-Path $env:USERPROFILE "Downloads\20261122_212600_569c5f.zip"),
  "D:\ISS 26\20261122_212600_569c5f.zip",
  "D:\ISS 26\ISS26_Data\explorer\20261122_212600_569c5f.zip"
 )
 $found=$names|Where-Object {Test-Path -LiteralPath $_}|Select-Object -First 1
 if(-not $found){
  foreach($root in @("D:\ISS 26\ISS26_Data\explorer","D:\ISS 26\ISS26_Data\reports")){
   if(Test-Path -LiteralPath $root){
    $file=Get-ChildItem -Path $root -Recurse -Filter "20261122_212600_569c5f.zip" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if($file){$found=$file.FullName;break}
   }
  }
 }
 if($found){$args+=@("--zip",$found)}
}
if(-not $NoPost -and (Get-Command gh.exe -ErrorAction SilentlyContinue)){$args+="--post-issue"}
& $python @args
if($LASTEXITCODE -ne 0){throw "DEV76 diagnostic failed (exit $LASTEXITCODE)."}
Write-Host "ISS26 DEV76: original game and patches were NOT modified."
Write-Host ("Read-only report: "+(Join-Path $base "DEV76-disc-runtime.json"))
