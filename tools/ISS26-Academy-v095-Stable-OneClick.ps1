#requires -Version 7.0
<#
ISS26 Academy + Updater 0.9.5 — one-click verified Windows release.
This publisher does not modify original PS1 files, saves, or the game-patch feed.
A failed compilation, verification, or upload does not move the auto-update feed.
#>
[CmdletBinding()]
param([string]$OutputDirectory = "")
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$expectedPrivateSha = "167f0d0952c8f7f77a535b613ea6f342cb83a564"
$publicScriptsCommit = "275836b99c86f3c44fbb49eb591c339bfc1dec61"
$base = "https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/$publicScriptsCommit/tools"
$folder = Join-Path ([IO.Path]::GetTempPath()) ("ISS26-095-release-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $folder -Force | Out-Null
try {
    foreach ($name in @(
        "Build-ISS26-Academy-v095-Stable-Local.ps1",
        "Release-ISS26-Academy-v095-Stable-Local.ps1"
    )) {
        $dest = Join-Path $folder $name
        Invoke-WebRequest -Uri "$base/$name" -OutFile $dest
        if (-not (Test-Path -LiteralPath $dest) -or
            -not [IO.File]::ReadAllText($dest).Contains($expectedPrivateSha)) {
            throw "Refusing to execute an unpinned release script: $name"
        }
    }
    $publisher = Join-Path $folder "Release-ISS26-Academy-v095-Stable-Local.ps1"
    $cmdArgs = @("-NoProfile","-ExecutionPolicy","Bypass","-File",$publisher)
    if ($OutputDirectory) { $cmdArgs += @("-OutputDirectory",$OutputDirectory) }
    & pwsh @cmdArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Release gate failed (code $LASTEXITCODE). The existing 0.9.6 feed is unchanged."
    }
    Write-Host "SUCCESS: ISS26 Academy + Updater 0.9.5 published and 0.9.6 upgrade bridge enabled."
}
finally {
    Write-Host "Release-script audit copies: $folder"
}
