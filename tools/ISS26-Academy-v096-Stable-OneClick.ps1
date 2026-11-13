# ISS26 Academy + Rookie v0.9.6 — one-file release bootstrap for Windows.
# No original game, BIOS, or existing ISS26 files are ever modified.
[CmdletBinding()]
param([string]$OutputDirectory = "")
$ErrorActionPreference = "Stop"
$publicCommit = "42255c9fc888305dd47f95be2ff8475334fd8ee6"
$expectedSource = "64780ba4bcc15765daf2982b452256bd02629a1b"
if (-not (Get-Command pwsh -ErrorAction SilentlyContinue)) {
    throw "PowerShell 7 is required. Install it from https://aka.ms/powershell"
}
$dir = Join-Path $env:TEMP ("ISS26-publish-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$base = "https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/$publicCommit/tools"
$builder = Join-Path $dir "Build-ISS26-Academy-v096-Stable-Local.ps1"
$publisher = Join-Path $dir "Release-ISS26-Academy-v096-Stable-Local.ps1"
foreach ($item in @(
    @{Path=$builder;Name="Build-ISS26-Academy-v096-Stable-Local.ps1"},
    @{Path=$publisher;Name="Release-ISS26-Academy-v096-Stable-Local.ps1"}
)) {
    $uri = $base + "/" + $item.Name
    Invoke-WebRequest -Uri $uri -UseBasicParsing -OutFile $item.Path
    if (-not (Test-Path $item.Path)) {
        throw "Could not retrieve pinned release tool: $uri"
    }
    $content = [IO.File]::ReadAllText($item.Path)
    if (-not $content.Contains($expectedSource)) {
        throw "Refusing to execute release script with mismatched source SHA"
    }
}
$callArgs = @("-NoProfile","-ExecutionPolicy","Bypass","-File",$publisher)
if (-not [string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $callArgs += @("-OutputDirectory",$OutputDirectory)
}
try {
    & pwsh @callArgs
    if ($LASTEXITCODE -ne 0) {
        throw "The stable release checks failed (exit $LASTEXITCODE). v0.9.4 remains in the stable feed."
    }
}
finally {
    # Retain the exact downloaded scripts so an interrupted session can
    # be reviewed; they are contained in an isolated temporary directory.
    Write-Host "Local release logs and scripts: $dir"
}
