#requires -Version 7.0
<#
ISS26 Academy Test27 - local Windows MIPS instrumentation preview builder.
Build and verify only. This script does not publish, change feeds, or change BIN/CUE.
Requires Windows, PowerShell 7, .NET SDK 8, Git, GitHub CLI authorized for
private Nevmerlyk/ISS26-Android and Python 3.
#>
[CmdletBinding()]
param([string]$OutputDirectory = "")
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repo = "Nevmerlyk/ISS26-Android"
$branch = "feature/academy-test23-ram-stage-transition"
$version = "0.9.5"
$expectedSha = "c157c8d91bf7ed5678d913c4bc0014c709e8da95"
function CheckLastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed (exit $LASTEXITCODE)" }
}
function FileHash([string]$path) {
    (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}
if (-not $IsWindows) { throw "This launcher must be built on Windows." }
foreach ($name in @("git", "gh", "dotnet")) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name is required."
    }
}
$sdk = @(dotnet --list-sdks)
CheckLastExit "dotnet SDK inventory"
if (-not ($sdk | Where-Object { $_ -match '^8\.' })) {
    throw ".NET SDK 8.x is required."
}
$pythonCommand = $null
$pythonArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
    $pythonArgs = @("-3")
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
}
else { throw "Python 3 is required for research triage regression." }
gh auth status
CheckLastExit "GitHub authentication"
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path (Get-Location).Path "ISS26_Academy_Test27_MIPS_preview"
}
$output = [IO.Path]::GetFullPath($OutputDirectory)
$work = Join-Path ([IO.Path]::GetTempPath()) ("ISS26-Academy-test27-preview-" + [guid]::NewGuid().ToString("N"))
$source = Join-Path $work "source"
$dist = Join-Path $work "dist"
$passed = $false
New-Item -ItemType Directory -Force -Path $work, $dist | Out-Null
Write-Host "Temporary build folder: $work"
Push-Location $work
try {
    gh repo clone $repo $source -- --branch $branch --single-branch --depth 1
    CheckLastExit "clone pinned Academy Test27 instrumentation branch"
    Push-Location $source
    try {
        $actualBranch = (git branch --show-current).Trim()
        CheckLastExit "git branch"
        if ($actualBranch -ne $branch) { throw "Unexpected source branch: $actualBranch" }
        $revision = (git rev-parse HEAD).Trim()
        CheckLastExit "git revision"
        if ($revision -ne $expectedSha) { throw "Source changed since review: $revision (expected $expectedSha)" }
        foreach ($project in @(
            "windows/ISS26.Launcher/ISS26.Launcher.csproj",
            "windows/ISS26.Updater/ISS26.Updater.csproj"
        )) {
            $xml = [xml](Get-Content -LiteralPath $project -Raw)
            if ([string]$xml.Project.PropertyGroup.Version -ne $version) {
                throw "Version mismatch in $project"
            }
        }
        $traceSrc = Get-Content -LiteralPath "windows/ISS26.Launcher/AcademyPrematchProvenanceLua.cs" -Raw
        foreach ($required in @("STAGE_COPY_DIMENSION_ANOMALY","STAGE_TRANSFER_RECT","STAGE_RECT_FINAL",
            "install(0x800387EC","install(0x8003878C")) {
            if (-not $traceSrc.Contains($required)) { throw "Missing Test27 source probe: $required" }
        }
        if ($traceSrc.Contains("if not x or w~=16 or h~=28 then return end")) {
            throw "Old 28-row-only filter still present; refusing preview"
        }
        & $pythonCommand @pythonArgs ".github/scripts/test_academy_research_triage.py"
        CheckLastExit "research triage regression"
        dotnet run --project "windows/ISS26.PortableTests/ISS26.PortableTests.csproj" -c Release
        CheckLastExit "Academy portable regression"
        foreach ($project in @(
            "windows/ISS26.Launcher/ISS26.Launcher.csproj",
            "windows/ISS26.Updater/ISS26.Updater.csproj"
        )) {
            dotnet publish $project -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:PublishTrimmed=false -o $dist
            CheckLastExit "publish $project"
        }
        foreach ($name in @("ISS26.exe", "ISS26.Updater.exe")) {
            $exe = Join-Path $dist $name
            if (-not (Test-Path -LiteralPath $exe)) { throw "Missing $name" }
            $file = Get-Item -LiteralPath $exe
            if ($file.Length -lt 1000000) { throw "Unexpected executable size for $name" }
            $bytes = [IO.File]::ReadAllBytes($exe)
            if ($bytes[0] -ne 77 -or $bytes[1] -ne 90) { throw "Invalid PE file: $name" }
            $v = [Diagnostics.FileVersionInfo]::GetVersionInfo($exe).FileVersion
            if (-not $v.StartsWith($version)) { throw "Wrong version for $name ($v)" }
        }
        $archive = Join-Path $dist "ISS26_Academy_Test27_MIPS_Preview.zip"
        Compress-Archive -LiteralPath @((Join-Path $dist "ISS26.exe"),(Join-Path $dist "ISS26.Updater.exe")) -DestinationPath $archive -CompressionLevel Optimal
        if ((Get-Item -LiteralPath $archive).Length -ge 160MB) { throw "Unexpected ZIP size" }
        Add-Type -AssemblyName System.IO.Compression
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        try {
            $entries = @($zip.Entries | ForEach-Object { $_.FullName })
            if ($entries.Count -ne 2 -or $entries -cnotcontains "ISS26.exe" -or $entries -cnotcontains "ISS26.Updater.exe") {
                throw "Unsafe or incomplete ZIP"
            }
            foreach ($name in $entries) {
                $member = $zip.GetEntry($name)
                $memberStream = $member.Open()
                try {
                    $memberHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($memberStream))
                }
                finally { $memberStream.Dispose() }
                if ($memberHash -ne (FileHash (Join-Path $dist $name))) {
                    throw "ZIP SHA256 mismatch for $name"
                }
            }
        }
        finally { $zip.Dispose() }
        New-Item -ItemType Directory -Force -Path $output | Out-Null
        $result = Join-Path $output (Split-Path $archive -Leaf)
        Copy-Item -LiteralPath $archive -Destination $result -Force
        $report = [ordered]@{
            schemaVersion = 1
            name = "ISS26 Academy Test27 read-only MIPS preview (NOT STABLE)"
            version = $version
            sourceRepo = $repo
            sourceBranch = $branch
            sourceCommit = $revision
            builtUtc = [DateTimeOffset]::UtcNow.ToString("O")
            tests = "Python triage and .NET portable: PASS"
            gamePatched = $false
            test27StageWriterCaptures16RowTransfers = $true
            previewNotStable = $true
            runtimePCSXVerificationPassed = $false
            stableFeedChanged = $false
            zipSha256 = FileHash $result
            launcherSha256 = FileHash (Join-Path $dist "ISS26.exe")
            updaterSha256 = FileHash (Join-Path $dist "ISS26.Updater.exe")
        }
        $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output "Academy_Test27_MIPS_Preview-build-report.json") -Encoding utf8
        Write-Host "PASS: Verified stable-build candidate ZIP: $result"
        Write-Host "SHA256: $($report.zipSha256)"
        Write-Host "Publishing is a separate gated step; original game remains unchanged."
        $passed = $true
    }
    finally { Pop-Location }
}
finally {
    Pop-Location
    if ($passed) { Remove-Item -LiteralPath $work -Recurse -Force }
    else { Write-Warning "Build failed; diagnostics remain at $work" }
}
