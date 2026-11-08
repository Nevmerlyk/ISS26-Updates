#requires -Version 5.1
<#
ISS26 Explorer v0.5.0 – no GitHub Actions release helper for Windows.
The old ISS26.exe will AUTO-UPDATE after this script successfully publishes:
  * a GitHub Release ZIP containing exactly ISS26.exe, ISS26.Updater.exe
  * a SHA-256 pinned launcher/latest.json pointing to that ZIP
This script is release engineering. It does not include game BIN/CUE or BIOS.
It does not change existing installations, original images or game saves.
PRE-REQ: .NET 8 SDK, git, GitHub CLI (gh) authenticated with repo write access.
Run ONCE on your Windows PC. Publishes only if every build/smoke gate passes.
#>
param(
  [switch]$BuildOnly,
  [switch]$SkipManualConfirmation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$version = "0.5.0"
$sourceRepo = "Nevmerlyk/ISS26-Android"
$releaseRepo = "Nevmerlyk/ISS26-Updates"
$sourceBranch = "feature/explorer-tool-dual-mode"
$pinnedCommit = "71536353c5b1517a13c895256c0b7bac4e32984e"
$tag = "launcher-v$version"
$assetName = "ISS26-LauncherUpdate.zip"
$url = "https://github.com/$releaseRepo/releases/download/$tag/$assetName"
$work = Join-Path ([IO.Path]::GetTempPath()) ("ISS26-Explorer-Release-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
$src = Join-Path $work "source"
$dist = Join-Path $work "binary"
$bundle = Join-Path $work $assetName
$manifestPath = Join-Path $work "candidate-launcher-latest.json"

function Require([string]$tool, [string]$how) {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
    throw "Missing required tool '$tool'. Install it and rerun. $how"
  }
}
function Sha([string]$file) {
  return (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToUpperInvariant()
}
function Assert([bool]$condition, [string]$message) {
  if (-not $condition) { throw $message }
}
function Github([string[]]$arguments) {
  & gh @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "gh command failed: gh $($arguments -join ' ')"
  }
}
function Smoke([string]$exe, [string]$dir) {
  $cue = Join-Path $dir "ISS Pro Evolution 2 (Europe) (En,Fr,De).cue"
  if (Test-Path -LiteralPath $cue) { throw "Unexpected original game CUE inside build directory" }
  $process = Start-Process -FilePath $exe -WorkingDirectory $dir -ArgumentList @("--mode", "play") -Wait -PassThru
  Assert ($process.ExitCode -eq 2) "No-CUE smoke test expected exit 2; got $($process.ExitCode)"
  Set-Content -LiteralPath $cue -Value "INVALID CUE" -Encoding ASCII
  try {
    $process = Start-Process -FilePath $exe -WorkingDirectory $dir -ArgumentList @("--mode", "play") -Wait -PassThru
    Assert ($process.ExitCode -eq 3) "Invalid-CUE smoke test expected exit 3; got $($process.ExitCode)"
  } finally {
    Remove-Item -LiteralPath $cue -Force -ErrorAction SilentlyContinue
  }
}

Write-Host "=== ISS26 Explorer $version: build and publish without GitHub Actions ==="
Require "dotnet" "Install .NET 8 SDK: winget install --id Microsoft.DotNet.SDK.8 -e"
Require "git" "Install Git: winget install --id Git.Git -e"
Require "gh" "Install GitHub CLI: winget install --id GitHub.cli -e"
$installedSdks = & dotnet --list-sdks
Assert (($installedSdks | Where-Object { $_ -match '^8\.' } | Measure-Object).Count -gt 0) ".NET 8 SDK is required"
Github @("auth", "status", "--hostname", "github.com")

New-Item -ItemType Directory -Force -Path $work, $dist | Out-Null
Write-Host "Cloning pinned source branch (no Actions minutes used)..."
Github @("repo", "clone", $sourceRepo, $src, "--", "--branch", $sourceBranch, "--single-branch")
$currentCommit = (& git -C $src rev-parse HEAD).Trim()
Assert ($LASTEXITCODE -eq 0) "git rev-parse failed"
Assert ($currentCommit -eq $pinnedCommit) "Source branch changed since review (expected $pinnedCommit, got $currentCommit); refusing unreviewed build."

$launcher = Join-Path $src "windows/ISS26.Launcher/ISS26.Launcher.csproj"
$updater = Join-Path $src "windows/ISS26.Updater/ISS26.Updater.csproj"
$tests = Join-Path $src "windows/ISS26.PortableTests/ISS26.PortableTests.csproj"

Write-Host "Compiling ISS26.exe with Windows Forms (self contained, x64)..."
& dotnet publish $launcher -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -o $dist
Assert ($LASTEXITCODE -eq 0) "ISS26.exe compilation failed. No release published."
Write-Host "Compiling ISS26.Updater.exe..."
& dotnet publish $updater -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -o $dist
Assert ($LASTEXITCODE -eq 0) "ISS26.Updater.exe compilation failed. No release published."

$exe = Join-Path $dist "ISS26.exe"
$helper = Join-Path $dist "ISS26.Updater.exe"
Assert ((Test-Path -LiteralPath $exe) -and (Test-Path -LiteralPath $helper)) "Missing compiled executable(s)"
$files = @($exe, $helper)
foreach($f in $files) {
  $bytes = [IO.File]::ReadAllBytes($f)
  Assert ($bytes.Length -gt 1000000) "Executable suspiciously small: $f"
  Assert ($bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A) "Bad PE (MZ) signature: $f"
  $fv = [Diagnostics.FileVersionInfo]::GetVersionInfo($f).FileVersion
  Assert ($fv.StartsWith("0.5.0")) "Wrong executable version: $f, $fv"
}

Write-Host "Running portable-data and stable-only channel unit checks..."
& dotnet run --project $tests --configuration Release
Assert ($LASTEXITCODE -eq 0) "Portable/stable channel tests failed. No release published."

Write-Host "Running headless executable smoke tests (must NOT launch gameplay)..."
Smoke $exe $dist
Write-Host "PASS: headless launcher returns 2 for absent CUE, 3 for invalid CUE."

Compress-Archive -LiteralPath $exe, $helper -DestinationPath $bundle -CompressionLevel Optimal
Add-Type -AssemblyName System.IO.Compression
$zip = [System.IO.Compression.ZipFile]::OpenRead($bundle)
try {
  $names = @($zip.Entries | ForEach-Object { $_.FullName } | Sort-Object)
  Assert ($names.Count -eq 2 -and $names[0] -eq "ISS26.Updater.exe" -and $names[1] -eq "ISS26.exe") "Updater ZIP contents must be exactly two EXEs."
} finally { $zip.Dispose() }

$manifest = [ordered]@{
  schemaVersion = 1
  latest = [ordered]@{
    version = $version
    zipUrl = $url
    zipSha256 = (Sha $bundle)
    launcherSha256 = (Sha $exe)
    updaterSha256 = (Sha $helper)
    notes = "ISS26 Explorer Tool 0.5.0: Play Game / Test Game, isolated diagnostics (experimental); no changes to source game images"
  }
}
$json = ($manifest | ConvertTo-Json -Depth 6)
[IO.File]::WriteAllText($manifestPath, $json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
Write-Host "Build and smoke checks PASS. Release candidate: $bundle"
Write-Host "Launcher SHA256: " $manifest.latest.launcherSha256
Write-Host "Updater SHA256:  " $manifest.latest.updaterSha256
Write-Host "ZIP SHA256:      " $manifest.latest.zipSha256
Write-Host "Candidate JSON:  $manifestPath"

if ($BuildOnly) {
  Write-Host "BuildOnly: no remote changes. Source and binary candidate remain in $work"
  return
}
if (-not $SkipManualConfirmation) {
  Write-Host "WARNING: publishing updates launcher/latest.json for ALL ISS26 users; Explorer is NOT in-game tested."
  $confirm = Read-Host "Type exactly PUBLISH to activate auto-update"
  if ($confirm -cne "PUBLISH") {
    Write-Host "Publication cancelled. Files preserved at $work"
    return
  }
}

# Abort if the tag is in use: never overwrite an existing published binary.
# release list exits successfully even when no such release is present.
$existingTags = @(& gh release list -R $releaseRepo -L 100 --json tagName --jq '.[].tagName')
Assert ($LASTEXITCODE -eq 0) "Cannot inspect existing releases"
if ($existingTags -contains $tag) {
  throw "Release $tag already exists; refusing to overwrite user-visible update."
}

Write-Host "Publishing release ZIP (no GitHub Actions)..."
Github @("release", "create", $tag, $bundle,
    "-R", $releaseRepo, "--target", "main", "--title",
    "ISS26 Explorer Tool v$version — user test", "--notes",
    "Launcher-only preview. Build source: $sourceRepo commit $pinnedCommit. Play/Test chooser; debug runtime auto-provisioned on first Test Game. No game, CD audio or BIOS included.",
    "--prerelease", "--latest=false")

# Verify the release asset via public CDN before activating the feed.
$verified = $false
$downloaded = Join-Path $work "public-asset-check.zip"
for($i=0; $i -lt 8; $i++) {
  try {
    Invoke-WebRequest -Uri $url -OutFile $downloaded -UseBasicParsing -TimeoutSec 45
    if ((Sha $downloaded) -eq $manifest.latest.zipSha256) {
      $verified = $true
      break
    }
  } catch {
    Start-Sleep -Seconds 5
  }
  Start-Sleep -Seconds 5
}
Assert $verified "Release asset is not publicly available/valid. Feed remains unchanged."

$feedEndpoint = "repos/$releaseRepo/contents/launcher/latest.json"
$old = (& gh api $feedEndpoint | ConvertFrom-Json)
Assert ($LASTEXITCODE -eq 0) "Cannot read current launcher feed"
$current = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($old.content -replace '\s','')))
$currentVersion = ($current | ConvertFrom-Json).latest.version
Assert ($currentVersion -eq "0.4.1") "Unexpected feed version $currentVersion; refusing to overwrite a different rollout."

# GitHub contents API: precise SHA compare-and-set update.
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json + [Environment]::NewLine))
$payload = @{
  message = "release: activate verified ISS26 Explorer Tool launcher v$version"
  content = $encoded
  sha = $old.sha
  branch = "main"
} | ConvertTo-Json -Compress
$payloadFile = Join-Path $work "feed-put.json"
[IO.File]::WriteAllText($payloadFile, $payload, (New-Object Text.UTF8Encoding($false)))
Github @("api", "-X", "PUT", $feedEndpoint, "--input", $payloadFile)

# Read back the updated API content; don't report success just from PUT status.
$again = (& gh api $feedEndpoint | ConvertFrom-Json)
Assert ($LASTEXITCODE -eq 0) "Cannot re-read updated feed"
$verifiedFeed = [Text.Encoding]::UTF8.GetString(
  [Convert]::FromBase64String(($again.content -replace '\s',''))) | ConvertFrom-Json
Assert ($verifiedFeed.latest.version -eq $version -and
        $verifiedFeed.latest.zipSha256 -eq $manifest.latest.zipSha256) "Published feed doesn't match release candidate."
Write-Host "SUCCESS: ISS26 Explorer $version launcher feed activated."
Write-Host "On the next launch the installed ISS26.exe v0.4.1 automatically updates and restarts."
Write-Host "Build & release logs/ZIP: $work"
