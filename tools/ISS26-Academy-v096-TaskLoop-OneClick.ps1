# ISS26 Academy + Rookie v0.9.6 Task Loop — build and publish verified Windows release.
[CmdletBinding()]
param([string]$OutputDirectory = "")
$ErrorActionPreference = "Stop"
$toolsCommit = "e1bd890733079f7ef20255c3146029ef01c8d65a"
$privateSource = "c80d2a35328ff67e5a663c3653ba38235fefc530"
if (!(Get-Command pwsh -ErrorAction SilentlyContinue)) { throw "PowerShell 7 is required." }
$dir=Join-Path $env:TEMP ("ISS26-taskloop-tools-"+[guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$base="https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/$toolsCommit/tools"
foreach ($name in @("Build-ISS26-Academy-v096-TaskLoop-Local.ps1","Release-ISS26-Academy-v096-TaskLoop-Local.ps1")) {
    $path=Join-Path $dir $name
    Invoke-WebRequest -Uri "$base/$name" -UseBasicParsing -OutFile $path
    if (!(Get-Content -LiteralPath $path -Raw).Contains($privateSource)) { throw "Unexpected source pin in $name" }
}
$publisher=Join-Path $dir "Release-ISS26-Academy-v096-TaskLoop-Local.ps1"
$arguments=@("-NoProfile","-ExecutionPolicy","Bypass","-File",$publisher)
if ($OutputDirectory) { $arguments+=@("-OutputDirectory",$OutputDirectory) }
& pwsh @arguments
if ($LASTEXITCODE -ne 0) { throw "Release did not complete (exit $LASTEXITCODE). Check preceding diagnostics." }
Write-Host "Release completed; verified Windows package and launcher feed."
