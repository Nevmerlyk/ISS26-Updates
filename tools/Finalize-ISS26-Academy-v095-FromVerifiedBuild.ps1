#requires -Version 7.0
<#
Complete an interrupted Academy/Updater 0.9.5 release using an existing
verified build. No compilation, force-push, game patch or save changes.
#>
[CmdletBinding()]
param([string]$BuildDirectory = "")
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = "Nevmerlyk/ISS26-Updates"
$tag = "launcher-v0.9.5"
$legacyTag = "launcher-v0.9.6"
$source = "81e8f0c28246a10ff4ebe84f0ea0877b02bde448"
$transport = "0.9.6.1"
if (-not $BuildDirectory) {
    $BuildDirectory = Join-Path (Join-Path (Get-Location).Path "ISS26_Academy_v095_stable") "build"
}
$BuildDirectory = [IO.Path]::GetFullPath($BuildDirectory)
$zipPath = Join-Path $BuildDirectory "ISS26-LauncherUpdate.zip"
$reportPath = Join-Path $BuildDirectory "Academy_v095_build-report.json"

function Need([bool]$ok, [string]$why) {
    if (-not $ok) { throw $why }
}
function CheckExit([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed: exit $LASTEXITCODE" }
}
function GhGet([string]$endpoint) {
    $lines = @(gh api $endpoint)
    CheckExit "GitHub GET $endpoint"
    return (($lines -join [Environment]::NewLine) | ConvertFrom-Json)
}
function HashFile([string]$file) {
    return (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToUpperInvariant()
}
function GitHubFile([string]$path) {
    return GhGet ("repos/" + $repo + "/contents/" + $path + "?ref=main")
}
function DecodeFile($obj) {
    $bytes = [Convert]::FromBase64String(([string]$obj.content -replace '\s',''))
    return [Text.Encoding]::UTF8.GetString($bytes)
}

Need (Test-Path -LiteralPath $zipPath) "Verified ZIP missing at $zipPath"
Need (Test-Path -LiteralPath $reportPath) "Build report missing at $reportPath"
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
Need ($report.version -eq "0.9.5" -and $report.sourceCommit -eq $source -and
      $report.sourceBranch -eq "release/academy-updater-v095-compat" -and
      $report.tests -eq "Python triage and .NET portable: PASS" -and
      $report.gamePatched -eq $false -and $report.stableFeedChanged -eq $false) "Build evidence/provenance does not match verified 0.9.5"
foreach ($key in @("zipSha256", "launcherSha256", "updaterSha256")) {
    Need (([string]$report.$key) -match '^[a-fA-F0-9]{64}$') "Invalid report hash $key"
}
$zipHash = HashFile $zipPath
Need ($zipHash -eq ([string]$report.zipSha256).ToUpperInvariant()) "ZIP SHA differs from build report"
Need ((Get-Item -LiteralPath $zipPath).Length -lt 160MB) "ZIP too large"
Add-Type -AssemblyName System.IO.Compression
$zip = [IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $names = @($zip.Entries | ForEach-Object { $_.FullName })
    Need ($names.Count -eq 2 -and $names -ccontains "ISS26.exe" -and
          $names -ccontains "ISS26.Updater.exe") "ZIP must contain exactly two expected EXEs"
    foreach ($name in $names) {
        $entry = $zip.GetEntry($name)
        Need ($entry.Length -ge 1MB -and $entry.Length -lt 160MB) "Invalid EXE size"
        $stream = $entry.Open()
        try { $exeHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)) }
        finally { $stream.Dispose() }
        $want = if ($name -eq "ISS26.exe") { $report.launcherSha256 } else { $report.updaterSha256 }
        Need ($exeHash -eq ([string]$want).ToUpperInvariant()) "Corrupt or mismatched $name"
    }
}
finally { $zip.Dispose() }

gh auth status
CheckExit "GitHub authentication"
$release = GhGet "repos/$repo/releases/tags/$tag"
$assets = @($release.assets | Where-Object { $_.name -eq "ISS26-LauncherUpdate.zip" })
Need ($assets.Count -eq 1) "Verified v0.9.5 GitHub asset missing"
Need ([long]$assets[0].size -eq (Get-Item -LiteralPath $zipPath).Length) "Remote ZIP size mismatch"
Need (([string]$assets[0].digest).Equals("sha256:$zipHash", [StringComparison]::OrdinalIgnoreCase)) "Remote ZIP SHA-256 mismatch"
$oldRelease = GhGet "repos/$repo/releases/tags/$legacyTag"
Need (@($oldRelease.assets | Where-Object { $_.name -eq "ISS26-LauncherUpdate.zip" }).Count -eq 1) "v0.9.6 recovery ZIP missing"

$gameBefore = GitHubFile "stable/latest.json"
$feedInfo = GitHubFile "launcher/latest.json"
$oldFeed = DecodeFile $feedInfo | ConvertFrom-Json
Need ($oldFeed.schemaVersion -eq 1 -and $oldFeed.latest.version -in @("0.9.6", $transport)) "Unexpected launcher feed; refusing overwrite"

if ($oldFeed.latest.version -eq $transport) {
    Need ($oldFeed.latest.zipSha256 -eq $zipHash -and
          $oldFeed.latest.launcherSha256 -eq $report.launcherSha256 -and
          $oldFeed.latest.updaterSha256 -eq $report.updaterSha256) "Another update is already live"
    Write-Host "Feed already contains exact verified 0.9.5 package."
}
else {
    $newFeed = [ordered]@{
        schemaVersion=1
        latest=[ordered]@{
            version=$transport
            zipUrl="https://github.com/$repo/releases/download/$tag/ISS26-LauncherUpdate.zip"
            zipSha256=$zipHash
            launcherSha256=([string]$report.launcherSha256).ToUpperInvariant()
            updaterSha256=([string]$report.updaterSha256).ToUpperInvariant()
            notes="ISS26 Academy/Updater PRODUCT 0.9.5. Transport 0.9.6.1 enables upgrades from installed 0.9.6; exact SHA-256 prevents repeats. Rookie adaptive menu and Test21 RAM/MIPS diagnostics. Game patch unchanged."
        }
    }
    $newText = ($newFeed | ConvertTo-Json -Depth 8) + [Environment]::NewLine
    $payload = @{
        message="release(academy): atomically promote verified 0.9.5 compatibility update"
        branch="main"
        sha=[string]$feedInfo.sha
        content=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($newText))
    } | ConvertTo-Json -Depth 6
    $request = Join-Path $env:TEMP ("iss26-feed-" + [guid]::NewGuid().ToString("N") + ".json")
    try {
        [IO.File]::WriteAllText($request,$payload,[Text.UTF8Encoding]::new($false))
        gh api --method PUT "repos/$repo/contents/launcher/latest.json" --input $request | Out-Null
        CheckExit "Atomic launcher feed update"
    }
    finally { if (Test-Path $request) { Remove-Item $request -Force } }
    Write-Host "Promoted: launcher feed now points to verified 0.9.5."
}
$live = DecodeFile (GitHubFile "launcher/latest.json") | ConvertFrom-Json
Need ($live.latest.version -eq $transport -and
      $live.latest.zipSha256 -eq $zipHash -and
      $live.latest.launcherSha256 -eq $report.launcherSha256 -and
      $live.latest.updaterSha256 -eq $report.updaterSha256) "Live feed verification failed"
$gameAfter = GitHubFile "stable/latest.json"
Need ($gameAfter.sha -eq $gameBefore.sha) "Game patch feed unexpectedly changed"

# Retire only after successful feed promotion; retain old download.
$marker = "ARCHIVED / SUPERSEDED: ISS26 Academy/Updater 0.9.6"
$notes = [string]$oldRelease.body
if (-not $notes.StartsWith($marker,[StringComparison]::Ordinal)) {
    $notes = $marker + [Environment]::NewLine +
        "Replaced by product 0.9.5. Historical v0.9.6 ZIP retained for recovery." +
        [Environment]::NewLine + [Environment]::NewLine + $notes
}
$notePath = Join-Path $env:TEMP ("iss26-retire-096-" + [guid]::NewGuid().ToString("N") + ".md")
try {
    [IO.File]::WriteAllText($notePath,$notes,[Text.UTF8Encoding]::new($false))
    gh release edit $legacyTag --repo $repo --prerelease=true --latest=false --title "ISS26 Academy v0.9.6 (ARCHIVED; replaced by 0.9.5)" --notes-file $notePath
    CheckExit "Archive old v0.9.6 release"
}
finally { if (Test-Path $notePath) { Remove-Item $notePath -Force } }
$archived = GhGet "repos/$repo/releases/tags/$legacyTag"
Need ($archived.prerelease -and
      @($archived.assets | Where-Object { $_.name -eq "ISS26-LauncherUpdate.zip" }).Count -eq 1) "Archival verification failed"
gh release edit $tag --repo $repo --prerelease=false --latest=true
CheckExit "Mark v0.9.5 as latest stable"
$latest = GhGet "repos/$repo/releases/latest"
Need ($latest.tag_name -eq $tag -and -not $latest.prerelease) "Latest stable release verification failed"
Write-Host "SUCCESS: Academy/Updater product 0.9.5 live. Auto-update transport: $transport."
Write-Host "v0.9.6 archived with ZIP preserved. Game patch and saves unchanged."
