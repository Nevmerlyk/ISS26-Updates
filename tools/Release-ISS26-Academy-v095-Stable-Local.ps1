#requires -Version 7.0
<#
ISS26 Academy + Rookie v0.9.5 — protected Windows stable publisher.
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
$version = "0.9.5"
$transportVersion = "0.9.6.1" # SemVer bridge for installed 0.9.6
$tag = "launcher-v$version"
$expectedCommit = "167f0d0952c8f7f77a535b613ea6f342cb83a564"
$runFolder = Join-Path ([IO.Path]::GetTempPath()) ("ISS26-publish-v095-" + [guid]::NewGuid().ToString("N"))
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path (Get-Location).Path "ISS26_Academy_v095_stable"
}
$output = [IO.Path]::GetFullPath($OutputDirectory)
$builder = Join-Path $PSScriptRoot "Build-ISS26-Academy-v095-Stable-Local.ps1"
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
$archive = Join-Path (Join-Path $output "ISS26_Academy_v095_stable_build") "ISS26-LauncherUpdate.zip"
# Builder uses its own default when no argument; pass an explicit safe path.
$buildOutput = Join-Path $output "build"
& $builder -OutputDirectory $buildOutput
RequireExit "Academy/Rookie portable regression and Windows build"
$archive = Join-Path $buildOutput "ISS26-LauncherUpdate.zip"
$reportPath = Join-Path $buildOutput "Academy_v095_build-report.json"
if (-not (Test-Path $archive) -or -not (Test-Path $reportPath)) {
    throw "Verified build archive/report absent; no stable channel changes"
}
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($report.version -ne $version -or
    $report.sourceCommit -ne $expectedCommit -or
    $report.sourceBranch -ne "release/academy-updater-v095-compat" -or
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
    if ([Version]$transportVersion -le [Version]"0.9.6") {
        throw "Transport version must be newer than installed 0.9.6"
    }
    if ($oldFeed.schemaVersion -ne 1 -or
        $oldFeed.latest.version -notin @("0.9.6","0.9.6.1")) {
        throw "Unexpected launcher stable channel: $($oldFeed.latest.version)"
    }
    if ($oldFeed.latest.version -eq $transportVersion -and
        $oldFeed.latest.zipSha256.ToUpperInvariant() -ne $zipSha) {
        throw "Another v0.9.5 is already live with different bits; refusing overwrite"
    }
    # Preflight retirement requirements before creating a new release.
    # An older 0.9.6 package must stay downloadable for recovery.
    $legacyTag = "launcher-v0.9.6"
    $legacyJson = gh api "repos/$publicRepo/releases/tags/$legacyTag"
    RequireExit "Read original v0.9.6 backup release"
    $legacyRelease = ($legacyJson -join "`n") | ConvertFrom-Json
    if ($legacyRelease.tag_name -ne $legacyTag -or
        @($legacyRelease.assets | Where-Object { $_.name -eq "ISS26-LauncherUpdate.zip" }).Count -ne 1) {
        throw "v0.9.6 recovery asset missing; refusing to change public release channel"
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
# ISS26 Academy + Updater 0.9.5 (Windows stable tools)
Source commit: $expectedCommit
Product version 0.9.5, transport compatibility version $transportVersion.
Installed 0.9.6 sees 0.9.6.1 as an update; 0.9.5 uses verified EXE hashes
to recognize the installed package and avoid a repeated update.
Validated local build: Python triage, .NET portable regression and Win-x64.
Contains Rookie adaptive intro/START/CIRCLE navigation, human-observed
exploratory hypotheses and Test21 RAM/MIPS flag provenance research.
Release ZIP contains ONLY ISS26.exe and ISS26.Updater.exe.
Game BIN/CUE, stable game patch, original BIOS, saves and Rookie data untouched.
A real autonomous five-minute Rookie exam remains to be verified.
"@ | Set-Content -LiteralPath $notesPath -Encoding utf8NoBOM
        gh release create $tag $archive --repo $publicRepo --title "ISS26 Academy + Rookie v0.9.5" --notes-file $notesPath --latest
        RequireExit "Publish stable Windows release"
    }
    # Verify the actually downloadable asset, not just gh release create.
    $remote = Join-Path $runFolder "remote-verify"
    New-Item -ItemType Directory -Force -Path $remote | Out-Null
    gh release download $tag --repo $publicRepo -p "ISS26-LauncherUpdate.zip" -D $remote
    RequireExit "Download uploaded release for independent verification"
    if ((HashOf (Join-Path $remote "ISS26-LauncherUpdate.zip")) -ne $zipSha) {
        throw "Remote release SHA-256 mismatch: stable feed remains unchanged"
    }
    # Publication of the GitHub release is necessary but not sufficient:
    # only after exact SHA validation can the stable launcher feed advance.
    $newFeed = [ordered]@{
        schemaVersion = 1
        latest = [ordered]@{
            version = $transportVersion
            zipUrl = "https://github.com/$publicRepo/releases/download/$tag/ISS26-LauncherUpdate.zip"
            zipSha256 = $zipSha
            launcherSha256 = $report.launcherSha256
            updaterSha256 = $report.updaterSha256
            notes = "Product: ISS26 Academy and Updater 0.9.5. Transport compatibility version 0.9.6.1 permits updating installed 0.9.6 and verified executable hashes prevent update loops. Rookie adaptive navigation and Test21 RAM/MIPS flag tracing. Game patch channel unchanged."
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
            git -c user.name="ISS26 Local Publisher" -c user.email="iss26-publisher@users.noreply.github.com" commit -m "release(academy): promote verified launcher v0.9.5 stable"
            RequireExit "Commit new stable launcher feed"
            git push origin HEAD:main
            RequireExit "Push verified launcher feed"
        }
        # Retire v0.9.6 ONLY after the v0.9.5 asset is verified and the
        # auto-update feed has been pushed. Preserve its binary asset for
        # disaster recovery and existing direct links; never delete/tag-move.
        $previousTag = "launcher-v0.9.6"
        $priorJson = gh api "repos/$publicRepo/releases/tags/$previousTag"
        RequireExit "Read previous Academy 0.9.6 release"
        $prior = ($priorJson -join "`n") | ConvertFrom-Json
        if ($prior.tag_name -ne $previousTag -or
            @($prior.assets | Where-Object { $_.name -eq "ISS26-LauncherUpdate.zip" }).Count -ne 1) {
            throw "Cannot safely archive v0.9.6: its backup asset is missing"
        }
        $archiveMarker = "ARCHIVED / SUPERSEDED: ISS26 Academy + Updater v0.9.6"
        $notes = [string]$prior.body
        if (-not $notes.StartsWith($archiveMarker,[StringComparison]::Ordinal)) {
            $notes = $archiveMarker + "`nReplaced by product v0.9.5 using transport v0.9.6.1." +
                "`nThe 0.9.6 installer is preserved for disaster recovery only." +
                "`nDo not install this version as the current stable release.`n`n" + $notes
        }
        $retiredNotes = Join-Path $runFolder "archived-v096-notes.md"
        [IO.File]::WriteAllText($retiredNotes,$notes,[Text.UTF8Encoding]::new($false))
        gh release edit $previousTag --repo $publicRepo --prerelease=true --latest=false --title "ISS26 Academy v0.9.6 (ARCHIVED — replaced by v0.9.5)" --notes-file $retiredNotes
        RequireExit "Archive superseded v0.9.6 without deleting its binary"
        $retired = (gh api "repos/$publicRepo/releases/tags/$previousTag" | ConvertFrom-Json)
        RequireExit "Verify v0.9.6 archived release"
        if (-not $retired.prerelease -or
            @($retired.assets | Where-Object { $_.name -eq "ISS26-LauncherUpdate.zip" }).Count -ne 1) {
            throw "v0.9.6 could not be verified as archived with a preserved asset"
        }
        gh release edit $tag --repo $publicRepo --prerelease=false --latest=true
        RequireExit "Confirm v0.9.5 is the latest stable release"
        $latest = (gh api "repos/$publicRepo/releases/latest" | ConvertFrom-Json)
        RequireExit "Verify GitHub latest stable release"
        if ($latest.tag_name -ne $tag -or $latest.prerelease) {
            throw "GitHub latest release is not the verified v0.9.5"
        }
        $reportStatus = [ordered]@{
            schemaVersion=1
            productVersion=$version
            updateTransport=$transportVersion
            latestTag=$tag
            archivedTag=$previousTag
            archivedAssetPreserved=$true
            deployedZipSha256=$zipSha
            completedUtc=[DateTimeOffset]::UtcNow.ToString("O")
        }
        $reportStatus | ConvertTo-Json -Depth 5 |
            Set-Content -LiteralPath (Join-Path $output "Academy_v095_release-status.json") -Encoding utf8NoBOM
        Write-Host "STABLE: Academy + Updater v0.9.5 published and auto-update feed promoted."
        Write-Host "ARCHIVED: v0.9.6 is now a prerelease; its binary ZIP remains downloadable."
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
