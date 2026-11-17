#requires -Version 7.0
# ISS26 Academy latest: one reusable Windows publisher (currently 0.9.6.5), no GitHub Actions.
# Build, validate, publish a single launcher release, then update launcher/latest.json.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'

$sourceRepo='Nevmerlyk/ISS26-Android'
$releaseRepo='Nevmerlyk/ISS26-Updates'
$sourceBranch='release/academy-autoresearch-v0965'
$sourceSha='c7b15bc86df01b81f483be0be4f64c835ff3dac6'
$version='0.9.6.5'
$tag='launcher-v0.9.6.5'
$remoteUrl="https://github.com/$releaseRepo/releases/download/$tag/ISS26-LauncherUpdate.zip"
$temp=Join-Path ([IO.Path]::GetTempPath()) ('ISS26-publish-'+[guid]::NewGuid().ToString('N'))

function Check([string]$name) {
  if ($LASTEXITCODE -ne 0) { throw "$name failed: exit $LASTEXITCODE" }
}
function Sha([string]$path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}
function RemoteFile([string]$path) {
  $raw=gh api "repos/$releaseRepo/contents/$path"
  Check "Read $path"
  $obj=$raw | ConvertFrom-Json
  $str=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($obj.content -replace '\s','')))
  return [pscustomobject]@{ sha=$obj.sha; data=($str | ConvertFrom-Json) }
}
function VerifyZip([string]$file,[string]$exeHash,[string]$helperHash) {
  $archive=[IO.Compression.ZipFile]::OpenRead($file)
  try {
    $list=@($archive.Entries | ForEach-Object { $_.FullName })
    if ($list.Count -ne 2 -or $list -cnotcontains 'ISS26.exe' -or $list -cnotcontains 'ISS26.Updater.exe') { throw 'Unexpected ZIP files' }
    foreach ($name in @('ISS26.exe','ISS26.Updater.exe')) {
      $entry=$archive.GetEntry($name)
      if (!$entry -or $entry.Length -lt 1000000 -or $entry.Length -gt 160MB) { throw "Invalid ZIP item $name" }
      $stream=$entry.Open()
      try { $actual=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)) }
      finally { $stream.Dispose() }
      $expected=if ($name -eq 'ISS26.exe') {$exeHash} else {$helperHash}
      if ($actual -ne $expected) { throw "ZIP checksum mismatch: $name" }
    }
  } finally { $archive.Dispose() }
}
if (!$IsWindows) { throw 'Run this command on Windows using PowerShell 7.' }
foreach ($name in @('git','gh','dotnet')) {
  if (!(Get-Command $name -ErrorAction SilentlyContinue)) { throw "Missing $name on PATH." }
}
$sdks=@(dotnet --list-sdks)
Check 'Read .NET SDK inventory'
if (!($sdks | Where-Object { $_ -match '^8\.' })) { throw '.NET 8 SDK is required.' }
$python=if (Get-Command py -ErrorAction SilentlyContinue) {'py'} elseif (Get-Command python -ErrorAction SilentlyContinue) {'python'} else {$null}
if (!$python) { throw 'Python 3 is required for Academy regression tests.' }
$pythonArgs=@()
if ($python -eq 'py') { $pythonArgs=@('-3') }
gh auth status
Check 'GitHub authorization'
gh api "repos/$sourceRepo" | Out-Null
Check 'Private Academy source access'
gh api "repos/$releaseRepo" | Out-Null
Check 'Update repository access'

$previous=RemoteFile 'launcher/latest.json'
if ($previous.data.schemaVersion -ne 1) { throw 'Unexpected launcher manifest schema.' }
if ($previous.data.latest.version -eq $version) {
  if ($previous.data.latest.zipUrl -ne $remoteUrl) { throw "Conflicting $version release" }
  Write-Host "Academy $version is already active. No changes needed." -ForegroundColor Green
  return
}
if ($previous.data.latest.version -ne '0.9.6.4') { throw "Unexpected launcher version $($previous.data.latest.version). Safe stop." }
$oldStable=RemoteFile 'stable/latest.json'
$oldTest=RemoteFile 'test/latest.json'

New-Item -ItemType Directory -Path $temp -Force | Out-Null
try {
  $src=Join-Path $temp 'source'
  $dist=Join-Path $temp 'package'
  $remote=Join-Path $temp 'verified'
  New-Item -ItemType Directory -Path $dist,$remote -Force | Out-Null
  Write-Host '[1/6] Checkout pinned Academy source'
  gh repo clone $sourceRepo $src -- --branch $sourceBranch --single-branch --depth 1
  Check 'Clone private source'
  Push-Location $src
  try {
    $current=(git rev-parse HEAD).Trim()
    Check 'Read source commit'
    if ($current -ne $sourceSha) { throw "Unexpected source revision: $current" }
    foreach ($file in @('windows/ISS26.Launcher/ISS26.Launcher.csproj','windows/ISS26.Updater/ISS26.Updater.csproj')) {
      $xml=[xml](Get-Content -LiteralPath $file -Raw)
      if ([string]$xml.Project.PropertyGroup.Version -ne $version) { throw "Wrong project version: $file" }
    }
    Write-Host '[2/6] Python and .NET regression tests'
    & $python @pythonArgs '.github/scripts/test_academy_research_triage.py'
    Check 'Python Academy tests'
    dotnet run --project windows/ISS26.PortableTests/ISS26.PortableTests.csproj -c Release
    Check '.NET portable tests'
    Write-Host '[3/6] Compiling Windows binaries'
    foreach ($proj in @('ISS26.Launcher','ISS26.Updater')) {
      dotnet publish "windows/$proj/$proj.csproj" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -o $dist
      Check "Publish $proj"
    }
  } finally { Pop-Location }

  foreach ($name in @('ISS26.exe','ISS26.Updater.exe')) {
    $file=Join-Path $dist $name
    if (!(Test-Path -LiteralPath $file)) { throw "Missing $name" }
    $info=Get-Item $file
    if ($info.Length -lt 1000000 -or $info.Length -ge 160MB) { throw "Invalid size: $name" }
    $f=[IO.File]::OpenRead($file)
    try {
      if ($f.ReadByte() -ne 77 -or $f.ReadByte() -ne 90) { throw "Not a Windows executable: $name" }
    } finally { $f.Dispose() }
    $v=[Diagnostics.FileVersionInfo]::GetVersionInfo($file).FileVersion
    if (!$v.StartsWith($version)) { throw "Wrong executable version: $name $v" }
  }
  $exeSha=Sha (Join-Path $dist 'ISS26.exe')
  $updaterSha=Sha (Join-Path $dist 'ISS26.Updater.exe')
  $zip=Join-Path $temp 'ISS26-LauncherUpdate.zip'
  Add-Type -AssemblyName System.IO.Compression
  $archive=[IO.Compression.ZipFile]::Open($zip,[IO.Compression.ZipArchiveMode]::Create)
  try {
    foreach ($name in @('ISS26.exe','ISS26.Updater.exe')) {
      $entry=$archive.CreateEntry($name,[IO.Compression.CompressionLevel]::Optimal)
      $entry.LastWriteTime=[DateTimeOffset]::Parse('2026-11-17T12:00:00Z')
      $f=[IO.File]::OpenRead((Join-Path $dist $name))
      $s=$entry.Open()
      try { $f.CopyTo($s) } finally { $s.Dispose();$f.Dispose() }
    }
  } finally { $archive.Dispose() }
  if ((Get-Item $zip).Length -ge 160MB) { throw 'Update ZIP exceeds maximum size' }
  VerifyZip $zip $exeSha $updaterSha
  $zipSha=Sha $zip

  Write-Host '[4/6] Publish and verify public GitHub release'
  $exists=$true
  $old=gh release view $tag -R $releaseRepo --json tagName,body 2>$null
  if ($LASTEXITCODE -ne 0) { $exists=$false }
  if ($exists) {
    $body=($old | ConvertFrom-Json).body
    if (!$body.Contains($sourceSha)) { throw 'Existing release has different or missing source SHA' }
  } else {
    $notes="Verified Academy $version from commit $sourceSha. Regression tests passed. " +
       'Integrated passive RAM/VRAM/screen research; no game disc or emulator package.'
    gh release create $tag $zip -R $releaseRepo --target main --latest=false --title "ISS26 Academy $version" --notes $notes
    Check 'Publish GitHub release'
  }
  gh release download $tag -R $releaseRepo -p ISS26-LauncherUpdate.zip -D $remote
  Check 'Download public release'
  if ((Sha (Join-Path $remote 'ISS26-LauncherUpdate.zip')) -ne $zipSha) { throw 'Published release SHA differs from build; no feed update' }
  VerifyZip (Join-Path $remote 'ISS26-LauncherUpdate.zip') $exeSha $updaterSha
  Write-Host '[5/6] Verify anonymous HTTPS package'
  $anonymous=Join-Path $temp 'anonymous.zip'
  $ok=$false
  for ($i=0;$i -lt 6;$i++) {
    try {
      Invoke-WebRequest -Uri $remoteUrl -OutFile $anonymous -TimeoutSec 90
      if ((Sha $anonymous) -eq $zipSha) { $ok=$true; break }
    } catch {}
    Start-Sleep -Seconds 5
  }
  if (!$ok) { throw 'Anonymous public download hash check failed; feed unchanged' }
  if ((RemoteFile 'stable/latest.json').sha -ne $oldStable.sha -or
      (RemoteFile 'test/latest.json').sha -ne $oldTest.sha) {
    throw 'Game patch channels changed concurrently; feed unchanged'
  }

  Write-Host '[6/6] Promote the verified self-update'
  $now=RemoteFile 'launcher/latest.json'
  if ($now.sha -ne $previous.sha -or $now.data.latest.version -ne '0.9.6.4') { throw 'Launcher feed changed concurrently; safe stop' }
  $manifest=[ordered]@{
    schemaVersion=1
    latest=[ordered]@{
      version=$version
      zipUrl=$remoteUrl
      zipSha256=$zipSha
      launcherSha256=$exeSha
      updaterSha256=$updaterSha
      notes='ISS26 Academy 0.9.6.5: continuous change-driven Master League RAM/VRAM/screen evidence; no pause or idle priority. Game Stable and Test untouched.'
    }
  }
  $json=$manifest | ConvertTo-Json -Depth 6
  $payload=@{
    branch='main'
    sha=$now.sha
    message='release: activate verified Academy 0.9.6.5 auto-update'
    content=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
  } | ConvertTo-Json -Compress
  $request=Join-Path $temp 'promote.json'
  [IO.File]::WriteAllText($request,$payload,[Text.UTF8Encoding]::new($false))
  gh api -X PUT "repos/$releaseRepo/contents/launcher/latest.json" --input $request | Out-Null
  Check 'Promote Academy update'
  $active=RemoteFile 'launcher/latest.json'
  if ($active.data.latest.version -ne $version -or $active.data.latest.zipSha256 -ne $zipSha -or $active.data.latest.zipUrl -ne $remoteUrl) { throw 'Published feed readback mismatch' }
  Write-Host ''
  Write-Host "SUCCESS: Academy $version auto-update is live." -ForegroundColor Green
  Write-Host 'Open the existing ISS26.exe. It will update itself.'
  Write-Host 'No game patch channels or original files were touched.'
} catch {
  Write-Host "PUBLISH FAILED: $($_.Exception.Message)" -ForegroundColor Red
  throw
} finally {
  Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
