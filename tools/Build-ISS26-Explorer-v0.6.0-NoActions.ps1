#requires -Version 5.1
<#
ISS26 Explorer Tool 0.6.0: local Windows build + tests, NO GitHub Actions.
This script NEVER publishes a release and NEVER updates launcher/latest.json.
Needs Windows with .NET 8 SDK and git. No game data or BIOS is distributed.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$version = '0.6.0'
$repo = 'https://github.com/Nevmerlyk/ISS26-Android.git'
$branch = 'feature/iss26-explorer-v060'
$pinnedCommit = '18f3514b2ab4313f9b745f4da16e3d5e01393ac1'
$work = Join-Path ([IO.Path]::GetTempPath()) ('ISS26-Explorer-060-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$source = Join-Path $work 'source'
$dist = Join-Path $work 'binary'
$zip = Join-Path $work 'ISS26-LauncherUpdate-v0.6.0-CANDIDATE.zip'

function Check([bool]$condition, [string]$message) {
  if (-not $condition) {throw $message}
}
function Tool([string]$name, [string]$instruction) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Missing $name. $instruction"
  }
}
function Hash([string]$path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}
function RunSmoke([string]$exe, [string]$dir) {
  $cue = Join-Path $dir 'ISS Pro Evolution 2 (Europe) (En,Fr,De).cue'
  Check (-not (Test-Path -LiteralPath $cue)) 'Original game is unexpectedly present in temp test dir.'
  $proc = Start-Process -FilePath $exe -WorkingDirectory $dir -ArgumentList '--mode','play' -PassThru -Wait
  Check ($proc.ExitCode -eq 2) "Play without CUE: expected 2, got $($proc.ExitCode)"
  Set-Content -LiteralPath $cue -Value 'INVALID CUE' -Encoding ASCII
  try {
    $proc = Start-Process -FilePath $exe -WorkingDirectory $dir -ArgumentList '--mode','play' -PassThru -Wait
    Check ($proc.ExitCode -eq 3) "Play invalid CUE: expected 3, got $($proc.ExitCode)"
    $quotedCue = '"' + $cue + '"'
    $proc = Start-Process -FilePath $exe -WorkingDirectory $dir -ArgumentList @('--mode','test','--cue',$quotedCue) -PassThru -Wait
    Check ($proc.ExitCode -eq 5) "Test invalid CUE: expected 5, got $($proc.ExitCode)"
    $reports = @(Get-ChildItem -Path (Join-Path $dir 'ISS26_Data\explorer\reports') -Filter 'ISS26_Session_*.zip' -File -ErrorAction Stop)
    Check ($reports.Count -ge 1) 'Test preflight must produce a diagnostic ZIP.'
    Write-Host ('PASS: Test preflight report ' + $reports[0].FullName)
  }
  finally {Remove-Item -LiteralPath $cue -Force -ErrorAction SilentlyContinue}
}

Write-Host ('=== ISS26 Explorer Tool v' + $version + ': candidate build, NO publication ===')
Tool 'dotnet' 'Install: winget install --id Microsoft.DotNet.SDK.8 -e'
Tool 'git' 'Install: winget install --id Git.Git -e'
$sdks = & dotnet --list-sdks
Check ((@($sdks | Where-Object {$_ -match '^8\.'})).Count -gt 0) '.NET 8 SDK is required.'
New-Item -ItemType Directory -Force -Path $work, $dist | Out-Null
& git clone --branch $branch --single-branch $repo $source
Check ($LASTEXITCODE -eq 0) 'git clone failed.'
$actual = (& git -C $source rev-parse HEAD).Trim()
Check ($LASTEXITCODE -eq 0) 'git rev-parse failed.'
Check ($actual -eq $pinnedCommit) ('Branch HEAD changed; expected ' + $pinnedCommit + ', got ' + $actual)
$tests = Join-Path $source 'windows/ISS26.PortableTests/ISS26.PortableTests.csproj'
$launcher = Join-Path $source 'windows/ISS26.Launcher/ISS26.Launcher.csproj'
$updater = Join-Path $source 'windows/ISS26.Updater/ISS26.Updater.csproj'
Write-Host 'Running portable test suite...'
& dotnet run --project $tests -c Release
Check ($LASTEXITCODE -eq 0) 'Portable tests failed. Source needs fixing; no publish.'
Write-Host 'Building Windows x64 launcher...'
& dotnet publish $launcher -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -o $dist
Check ($LASTEXITCODE -eq 0) 'ISS26.exe compilation failed.'
Write-Host 'Building Windows x64 update helper...'
& dotnet publish $updater -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -o $dist
Check ($LASTEXITCODE -eq 0) 'ISS26.Updater.exe compilation failed.'
$exe = Join-Path $dist 'ISS26.exe'
$helper = Join-Path $dist 'ISS26.Updater.exe'
foreach ($f in @($exe,$helper)) {
  Check (Test-Path -LiteralPath $f -PathType Leaf) ('Output missing: ' + $f)
  $info = [Diagnostics.FileVersionInfo]::GetVersionInfo($f)
  Check ($info.FileVersion.StartsWith($version)) ('Unexpected version in ' + $f)
}
Write-Host 'Running non-graphical launch smoke checks...'
RunSmoke $exe $dist

Compress-Archive -LiteralPath $exe, $helper -DestinationPath $zip -CompressionLevel Optimal
Add-Type -AssemblyName System.IO.Compression
$reader = [IO.Compression.ZipFile]::OpenRead($zip)
try {
  $files = @($reader.Entries | ForEach-Object {$_.FullName} | Sort-Object)
  Check ($files.Count -eq 2 -and
         $files -contains 'ISS26.exe' -and
         $files -contains 'ISS26.Updater.exe') 'Candidate ZIP contains unexpected files.'
}
finally {$reader.Dispose()}
$report = [ordered]@{
  version = $version
  commit = $pinnedCommit
  publisher = 'none, BuildOnly'
  zip = $zip
  zipSha256 = Hash $zip
  launcherSha256 = Hash $exe
  updaterSha256 = Hash $helper
  note = 'Candidate only. Do not update launcher/latest.json until Windows Ghost-mode crash and normal session report gates pass.'
}
$manifest = Join-Path $work 'candidate-build.json'
[IO.File]::WriteAllText($manifest,
    ($report | ConvertTo-Json -Depth 5) + [Environment]::NewLine,
    (New-Object System.Text.UTF8Encoding($false)))
Write-Host 'PASS: Portable test suite + Windows EXEs + headless smoke.'
Write-Host ('Build output: ' + $dist)
Write-Host ('ZIP candidate: ' + $zip)
Write-Host ('SHA256: ' + $report.zipSha256)
Write-Host 'NOT PUBLISHED: manual Ghost Mode and crashes remain to be verified.'
