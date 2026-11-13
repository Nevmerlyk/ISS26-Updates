#requires -Version 7.0
<#
ISS26 Academy + Rookie v0.9.6 — protected Windows stable publisher.
Runs deterministic private-source build/tests and publishes exactly TWO
Windows executables, never modifies game patch feed or original BIN/CUE.
GitHub CLI must have write access to Nevmerlyk/ISS26-Updates and read access
to Nevmerlyk/ISS26-Android. Failed validation leaves v0.9.4 live.
#>
[CmdletBinding()]
param([string]$OutputDirectory = "")
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$publicRepo = "Nevmerlyk/ISS26-Updates"
$version = "0.9.6"
$tag = "launcher-v$version"
$expectedCommit = "2d437b3bde5e651803632c8d38f74fdedc5b3fc1"
$runFolder = Join-Path ([IO.Path]::GetTempPath()) ("ISS26-publish-v096-" + [guid]::NewGuid().ToString("N"))
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path (Get-Location).Path "ISS26_Academy_v096_stable"
}
$output = [IO.Path]::GetFullPath($OutputDirectory)
$builder = Join-Path $PSScriptRoot "Build-ISS26-Academy-v096-Stable-Local.ps1"
if (-not (Test-Path -LiteralPath $builder)) {
    throw "Stable builder missing next to publisher: $builder"
}
foreach ($cmd in @("gh","git","dotnet","pwsh")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Missing requirement: $cmd"
    }
}
function RequireExit([string]$name) {
    if ($LASTEXITCODE -ne 0) { throw "$name failed (exit code $LASTEXITCODE)" }
}
function HashOf([string]$file) {
    (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToUpperInvariant()
}
$archive = Join-Path (Join-Path $output "ISS26_Academy_v096_stable_build") "ISS26-LauncherUpdate.zip"
# Builder uses its own default when no argument; pass an explicit safe path.
$buildOutput = Join-Path $output "build"
& $builder -OutputDirectory $buildOutput
RequireExit "Academy/Rookie portable regression and Windows build"
$archive = Join-Path $buildOutput "ISS26-LauncherUpdate.zip"
$reportPath = Join-Path $buildOutput "Academy_v096_build-report.json"
if (-not (Test-Path $archive) -or -not (Test-Path $reportPath)) {
    throw "Verified build archive/report absent; no stable channel changes"
}
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($report.version -ne $version -or
    $report.sourceCommit -ne $expectedCommit -or
    $report.sourceBranch -ne "stable/academy-v0.9.6-source" -or
    $report.tests -ne "Python triage and .NET portable: PASS" -or
    [bool]$report.gamePatched -or
    (HashOf $archive) -ne $report.zipSha256) {
    throw "Build provenance/checksum mismatch; refusing to publish"
}
$zipSha = HashOf $archive
# Separate pinned executable hashes are checked by the build script.
New-Item -ItemType Directory -Force -Path $runFolder | Out-Null
$checkout = Join-Path $runFolder "public"
try {
    gh auth status
    RequireExit "GitHub authentication"
    gh repo clone $publicRepo $checkout -- --single-branch --branch main --depth 1
    RequireExit "Public update repository clone"
    $feedPath = Join-Path $checkout "launcher/latest.json"
    $gameFeed = Join-Path $checkout "stable/latest.json"
    if (-not (Test-Path $feedPath) -or -not (Test-Path $gameFeed)) {
        throw "Missing existing stable feeds"
    }
    $oldGameHash = HashOf $gameFeed
    $oldFeed = Get-Content -LiteralPath $feedPath -Raw | ConvertFrom-Json
    if ($oldFeed.schemaVersion -ne 1 -or
        $oldFeed.latest.version -notin @("0.9.4","0.9.6")) {
        throw "Unexpected launcher stable channel: $($oldFeed.latest.version)"
    }
    if ($oldFeed.latest.version -eq "0.9.6" -and
        $oldFeed.latest.zipSha256.ToUpperInvariant() -ne $zipSha) {
        throw "Another v0.9.6 is already live with different bits; refusing overwrite"
    }
    $released = @(gh release list --repo $publicRepo --limit 100 --json tagName |
        ConvertFrom-Json)
    RequireExit "Read public releases"
    $alreadyExists = @($released | Where-Object { $_.tagName -eq $tag }).Count -gt 0
    if ($alreadyExists) {
        # Recover safely from a previous interrupted publish by verifying the
        # actual uploaded release archive before attempting feed promotion.
        $download = Join-Path $runFolder "verify-remote"
        New-Item -ItemType Directory -Force -Path $download | Out-Null
        gh release download $tag --repo $publicRepo -p "ISS26-LauncherUpdate.zip" -D $download
        RequireExit "Verify existing release asset"
        if ((HashOf (Join-Path $download "ISS26-LauncherUpdate.zip")) -ne $zipSha) {
            throw "Tag exists with a DIFFERENT asset checksum; refusing feed promotion"
        }
    }
    else {
        $notesPath = Join-Path $runFolder "stable-release-notes.md"
        @"
# ISS26 Academy + Rookie v0.9.6 (Windows stable tools)
Source commit: $expectedCommit
Validated build: .NET portable regression + private Rookie triage regression.
Includes expanded European PS1 menu theory, ten trials per visual screen,
five-minute Rookie exam, bounded dead-end recovery and live Academy decision
trace, immediate opt-in per-session private GitHub report delivery.
Installer ZIP includes ISS26.exe and ISS26.Updater.exe ONLY.
This release does NOT include the commercial game, PS1 BIOS, stable game
patch modifications or user's memory-card data.
The Rookie practical exam still requires real game session evidence:
declaring a tool release stable does not artificially award exam success.
"@ | Set-Content -LiteralPath $notesPath -Encoding utf8NoBOM
        gh release create $tag $archive --repo $publicRepo --title "ISS26 Academy + Rookie v0.9.6" --notes-file $notesPath --latest
        RequireExit "Publish stable Windows release"
    }
    # Publication of the GitHub release is necessary but not sufficient:
    # only after exact SHA validation can the stable launcher feed advance.
    $newFeed = [ordered]@{
        schemaVersion = 1
        latest = [ordered]@{
            version = $version
            zipUrl = "https://github.com/$publicRepo/releases/download/$tag/ISS26-LauncherUpdate.zip"
            zipSha256 = $zipSha
            launcherSha256 = $report.launcherSha256
            updaterSha256 = $report.updaterSha256
            notes = "Stable Academy and Rookie v0.9.6: five-minute practical exam, expanded navigation theory, live decision trace, opt-in report after every session. Game patch channel unchanged."
        }
    }
    $newFeed | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $feedPath -Encoding utf8NoBOM
    if ((HashOf $gameFeed) -ne $oldGameHash) {
        throw "Game patch stable feed changed unexpectedly; refusing promotion"
    }
    Push-Location $checkout
    try {
        git add -- launcher/latest.json
        RequireExit "Stage launcher feed"
        $changes = git status --porcelain
        RequireExit "Check feed diff"
        if ($changes) {
            git -c user.name="ISS26 Local Publisher" -c user.email="iss26-publisher@users.noreply.github.com" commit -m "release(academy): promote verified launcher v0.9.6 stable"
            RequireExit "Commit new stable launcher feed"
            git push origin HEAD:main
            RequireExit "Push verified launcher feed"
        }
        Write-Host "STABLE: Academy + Rookie v0.9.6 release and launcher feed published."
        Write-Host "Version: $version; source: $expectedCommit"
        Write-Host "SHA256: $zipSha"
        Write-Host "Original game and stable/latest.json unchanged."
    }
    finally { Pop-Location }
}
finally {
    if (Test-Path -LiteralPath $runFolder) {
        Remove-Item -LiteralPath $runFolder -Recurse -Force
    }
}
