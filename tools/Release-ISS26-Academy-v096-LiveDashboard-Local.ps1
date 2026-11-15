#requires -Version 7.0
# ISS26 Academy/Rookie 0.9.6 Task Loop — verified Windows publisher.
# The historical 0.9.6 and current 0.9.5 releases remain downloadable.
[CmdletBinding()]
param([string]$OutputDirectory = "")
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repo = "Nevmerlyk/ISS26-Updates"
$version = "0.9.6"
$transport = "0.9.6.3"
$tag = "launcher-v0.9.6-livedashboard"
$source = "03bba11a2de9327b7c568e52fb6d0904198c7339"
$branch = "feature/academy-v096-rookie-live-dashboard"
$builder = Join-Path $PSScriptRoot "Build-ISS26-Academy-v096-LiveDashboard-Local.ps1"
if (!$IsWindows) { throw "Windows required" }
if (!(Test-Path -LiteralPath $builder)) { throw "Pinned builder missing" }
if (!$OutputDirectory) { $OutputDirectory = Join-Path (Get-Location).Path "ISS26_Academy_v096_LiveDashboard_Release" }
$output = [IO.Path]::GetFullPath($OutputDirectory)
$build = Join-Path $output "build"
$zip = Join-Path $build "ISS26-LauncherUpdate.zip"
$reportPath = Join-Path $build "Academy_v096_livedashboard_build-report.json"
function Check([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed (exit $LASTEXITCODE)" }
}
function Hash([string]$path) {
    (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}
foreach ($program in @("gh","git","dotnet","pwsh")) {
    if (!(Get-Command $program -ErrorAction SilentlyContinue)) { throw "Missing $program" }
}
# Reuse only the exact verified local build on a publication retry. This avoids
# producing a different ZIP for a release tag whose asset already exists.
if (!(Test-Path -LiteralPath $zip) -or !(Test-Path -LiteralPath $reportPath)) {
    & pwsh -NoProfile -ExecutionPolicy Bypass -File $builder -OutputDirectory $build
    Check "Windows build and regression tests"
}
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($report.version -ne $version -or $report.sourceCommit -ne $source -or
    $report.sourceBranch -ne $branch -or
    $report.tests -ne "Python triage and .NET portable: PASS" -or
    $report.gamePatched -ne $false -or $report.stableFeedChanged -ne $false -or
    (Hash $zip) -ne $report.zipSha256) { throw "Build report mismatch; no publication" }
$zipHash=Hash $zip
# Recheck both ZIP members independently, including a reused build.
$archive=[IO.Compression.ZipFile]::OpenRead($zip)
try {
    if ($archive.Entries.Count -ne 2) { throw "Unexpected ZIP entries" }
    foreach ($member in @(
        @{Name="ISS26.exe"; Sha=$report.launcherSha256},
        @{Name="ISS26.Updater.exe"; Sha=$report.updaterSha256}
    )) {
        $entry=$archive.GetEntry($member.Name)
        if ($null -eq $entry -or $member.Sha -notmatch '^[A-Fa-f0-9]{64}$') { throw "Invalid build member" }
        $stream=$entry.Open()
        try { $actual=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)) }
        finally { $stream.Dispose() }
        if ($actual -ne $member.Sha) { throw "Executable SHA mismatch" }
    }
}
finally { $archive.Dispose() }
$work=Join-Path ([IO.Path]::GetTempPath()) ("ISS26-livedashboard-release-"+[guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work -Force | Out-Null
$checkout=Join-Path $work "updates"
try {
    gh auth status
    Check "GitHub authentication"
    gh repo clone $repo $checkout -- --branch main --single-branch --depth 1
    Check "Clone update repository"
    $feedPath=Join-Path $checkout "launcher/latest.json"
    $gamePath=Join-Path $checkout "stable/latest.json"
    $testPath=Join-Path $checkout "test/latest.json"
    $gameHash=Hash $gamePath
    $testHash=Hash $testPath
    $old=Get-Content -LiteralPath $feedPath -Raw | ConvertFrom-Json
    $url="https://github.com/$repo/releases/download/$tag/ISS26-LauncherUpdate.zip"
    if ($old.schemaVersion -ne 1 -or $old.latest.version -notin @("0.9.6.2",$transport)) {
        throw "Unexpected launcher feed; refusing downgrade"
    }
    if ($old.latest.version -eq "0.9.6.2" -and
        $old.latest.zipUrl -ne "https://github.com/$repo/releases/download/launcher-v0.9.6-taskloop/ISS26-LauncherUpdate.zip") {
        throw "Unexpected current release; refusing overwrite"
    }
    if ($old.latest.version -eq $transport -and
        ($old.latest.zipSha256 -ne $zipHash -or $old.latest.zipUrl -ne $url)) {
        throw "Different package already occupies this transport version"
    }
    $releases=gh release list --repo $repo --limit 100 --json tagName
    Check "Read release tags"
    $tags=@($releases | ConvertFrom-Json)
    if (!($tags | Where-Object { $_.tagName -eq $tag })) {
        $notes=Join-Path $work "release-notes.md"
        @"
# ISS26 Academy + Rookie 0.9.6 — Live Dashboard
Product 0.9.6; update transport $transport; source $source.
Validated local build: Python and .NET portable tests, Win-x64, ZIP SHA-256.
Rolling emulator preview, full controller and Academy journal, archived session review,
CRLF knowledge restoration, kickoff audit and concurrent passive scene capture.
Requires one-time opt-in private Issues access for report delivery.
Real emulator task execution and end-to-end private report delivery still need field verification.
Only ISS26.exe and ISS26.Updater.exe; no commercial game, BIOS or saves.
Previous releases and stable game patch feed are preserved.
"@ | Set-Content -LiteralPath $notes -Encoding utf8NoBOM
        gh release create $tag $zip --repo $repo --prerelease --title "ISS26 Academy + Rookie v0.9.6 - Live Dashboard" --notes-file $notes
        Check "Upload new release candidate"
    }
    $verify=Join-Path $work "verify"
    New-Item -ItemType Directory -Path $verify -Force | Out-Null
    gh release download $tag --repo $repo -p "ISS26-LauncherUpdate.zip" -D $verify
    Check "Download remote ZIP"
    if ((Hash (Join-Path $verify "ISS26-LauncherUpdate.zip")) -ne $zipHash) {
        throw "Remote ZIP differs from verified build; no feed promotion"
    }
    # Keep candidate marked prerelease until field validation. Explicit owner execution
    # upgrades the launcher feed after the build/tests and remote ZIP checks.
    $candidate=gh release view $tag --repo $repo --json tagName,isPrerelease
    Check "Check candidate release"
    $release=$candidate | ConvertFrom-Json
    if ($release.tagName -ne $tag -or !$release.isPrerelease) { throw "Candidate release verification failed" }
    $new=[ordered]@{
        schemaVersion=1
        latest=[ordered]@{
            version=$transport
            zipUrl=$url
            zipSha256=$zipHash
            launcherSha256=$report.launcherSha256
            updaterSha256=$report.updaterSha256
            notes="Product 0.9.6 Live Dashboard: live frame, session journals, restored skill imports and concurrent Academy capture. Transport 0.9.6.3 upgrades prior 0.9.6.2. Game patch unchanged."
        }
    }
    $new | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $feedPath -Encoding utf8NoBOM
    if ((Hash $gamePath) -ne $gameHash -or (Hash $testPath) -ne $testHash) { throw "Game feed unexpectedly changed" }
    Push-Location $checkout
    try {
        git add -- launcher/latest.json
        Check "Stage launcher feed"
        $changes=git diff --cached --name-only
        Check "Check staged paths"
        if ($changes) {
            if (@($changes).Count -ne 1 -or $changes -ne "launcher/latest.json") { throw "Unexpected staged paths" }
            git -c user.name="ISS26 Local Publisher" -c user.email="iss26-publisher@users.noreply.github.com" commit -m "release(academy): verified 0.9.6 Live Dashboard"
            Check "Commit launcher feed"
            git push origin HEAD:main
            Check "Push launcher feed"
        }
    } finally { Pop-Location }
    $remoteFeed=gh api "repos/$repo/contents/launcher/latest.json?ref=main"
    Check "Read remote launcher feed"
    $data=$remoteFeed | ConvertFrom-Json
    $verified=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($data.content)) | ConvertFrom-Json
    if ($verified.latest.version -ne $transport -or $verified.latest.zipSha256 -ne $zipHash -or $verified.latest.zipUrl -ne $url) {
        throw "Remote feed verification failed"
    }
    [ordered]@{productVersion=$version;transportVersion=$transport;sourceCommit=$source;tag=$tag;
        zipSha256=$zipHash;publishedUtc=[DateTimeOffset]::UtcNow.ToString("O")} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output "release-status.json") -Encoding utf8NoBOM
    Write-Host "PUBLISHED PREVIEW: Academy + Rookie 0.9.6 published; transport 0.9.6.3 verified."
    Write-Host "Game patch and historical releases unchanged."
}
finally {
    Write-Host "Release diagnostics: $work"
}
