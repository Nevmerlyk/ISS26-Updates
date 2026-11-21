# Complete the already-built Academy 0.9.6.15 update without recompiling.
# Does not touch BIN/CUE, saves, Stable PS1 patch or any local game folders.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$v = "0.9.6.15"
$previous = "0.9.6.14"
$updates = "Nevmerlyk/ISS26-Updates"
$tag = "launcher-v$v"
$url = "https://github.com/$updates/releases/download/$tag/ISS26-LauncherUpdate.zip"
$expectedZipHash = "D57BAF6D2E3ADD01BD00834E82CE67DC343A13DDCE45CE812C29698D2C4BB79B"
$root = Join-Path $env:LOCALAPPDATA "ISS26\releases\academy-$v"
$out = Join-Path $root "output"
$logs = Join-Path $root "logs"
New-Item -Path $logs -ItemType Directory -Force | Out-Null
Start-Transcript -LiteralPath (Join-Path $logs "finalize.log") -Append | Out-Null

function Hash([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Gh([string[]]$parts) {
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & gh @parts 2>&1
        $exit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    if ($exit -ne 0) {
        throw "GitHub CLI error (exit $exit): $($output -join ' ')"
    }
    return ($output -join [Environment]::NewLine)
}

function Meta([string]$path) {
    return (Gh @("api", "repos/$updates/contents/$path") | ConvertFrom-Json)
}

function Feed([object]$meta) {
    return ([Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String(($meta.content -replace '\s+', ''))) |
        ConvertFrom-Json)
}

try {
    if ($env:OS -ne "Windows_NT") { throw "This script requires Windows." }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI (gh) not found. The earlier publisher installed it."
    }
    $launcher = Join-Path $out "binaries\ISS26.exe"
    $updater = Join-Path $out "binaries\ISS26.Updater.exe"
    $candidate = Join-Path $out "ISS26-DEV56-LOCAL-ONLY.zip"
    $verifiedPublic = Join-Path $out "verified-public.zip"

    foreach ($file in @($launcher, $updater, $candidate)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Missing compiled file: $file. No feed was changed."
        }
    }

    foreach ($file in @($launcher, $updater)) {
        $actualVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo($file).FileVersion
        if (-not $actualVersion.StartsWith($v, [StringComparison]::Ordinal)) {
            throw "Wrong executable version in $file ($actualVersion). No feed was changed."
        }
    }
    if ((Get-Item -LiteralPath $candidate).Length -gt 160MB) {
        throw "ZIP exceeds updater size limit."
    }
    $ziphash = Hash $candidate
    if ($ziphash -ne $expectedZipHash) {
        throw "Local candidate differs from the existing GitHub release ZIP. No feed changed."
    }

    Add-Type -AssemblyName System.IO.Compression -ErrorAction Stop
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
    $zip = [IO.Compression.ZipFile]::OpenRead($candidate)
    try {
        $names = @($zip.Entries | ForEach-Object { $_.FullName })
        if ($names.Count -ne 2 -or
            $names -cnotcontains "ISS26.exe" -or
            $names -cnotcontains "ISS26.Updater.exe") {
            throw "Unexpected ZIP entries."
        }
        foreach ($entry in $zip.Entries) {
            if ($entry.Length -lt 1000000 -or $entry.Length -gt 160MB) {
                throw "Invalid executable entry size."
            }
            $source = if ($entry.FullName -ceq "ISS26.exe") { $launcher } else { $updater }
            $stream = $entry.Open()
            try {
                $sha = [Security.Cryptography.SHA256]::Create()
                try {
                    $entryHash = [BitConverter]::ToString(
                        $sha.ComputeHash($stream)).Replace("-", "")
                } finally { $sha.Dispose() }
            } finally { $stream.Dispose() }
            if ($entryHash -ne (Hash $source)) {
                throw "ZIP does not contain the tested executable: $($entry.FullName)"
            }
        }
    } finally { $zip.Dispose() }

    # The previous run already downloaded and hash-verified this exact asset.
    # If its cache was cleaned, download again before altering any metadata.
    if (-not (Test-Path -LiteralPath $verifiedPublic -PathType Leaf) -or
        (Hash $verifiedPublic) -ne $ziphash) {
        Invoke-WebRequest -Uri $url -OutFile $verifiedPublic -UseBasicParsing -TimeoutSec 180
    }
    if ((Hash $verifiedPublic) -ne $ziphash) {
        throw "Public release differs from verified local binaries."
    }

    $release = Gh @("api", "repos/$updates/releases/tags/$tag") | ConvertFrom-Json
    $asset = @($release.assets | Where-Object {
        $_.name -ceq "ISS26-LauncherUpdate.zip" -and $_.state -eq "uploaded"
    })
    if ($asset.Count -ne 1 -or
        $asset[0].digest -ne ("sha256:" + $ziphash.ToLowerInvariant())) {
        throw "GitHub release asset digest is not the verified candidate digest."
    }

    $game = Meta "stable/latest.json"
    $launcherHash = Hash $launcher
    $updaterHash = Hash $updater
    $body = @{
        schemaVersion = 1
        latest = @{
            version = $v
            zipUrl = $url
            zipSha256 = $ziphash
            launcherSha256 = $launcherHash
            updaterSha256 = $updaterHash
            notes = "Academy 0.9.6.15: Practice actions remain visible above the status bar. Stable PS1 game patch unchanged."
        }
    } | ConvertTo-Json -Depth 8
    $payloadFile = Join-Path $out "finalize-feed.json"

    for ($attempt = 1; $attempt -le 4; $attempt++) {
        $feedMeta = Meta "launcher/latest.json"
        $state = Feed $feedMeta
        if ($state.latest.version -eq $v) {
            if ($state.latest.zipSha256 -eq $ziphash -and
                $state.latest.launcherSha256 -eq $launcherHash -and
                $state.latest.updaterSha256 -eq $updaterHash) {
                Write-Host "PUBLISHED: ISS26 Academy $v is already active." -ForegroundColor Green
                return
            }
            throw "Different $v binaries are already active. Refusing overwrite."
        }
        if ($state.latest.version -ne $previous) {
            throw "Live launcher version is $($state.latest.version), expected $previous. Refusing overwrite."
        }
        if ((Meta "stable/latest.json").sha -ne $game.sha) {
            throw "Game Stable manifest changed. Refusing publication."
        }

        $req = @{
            branch = "main"
            sha = $feedMeta.sha
            message = "Activate verified ISS26 Academy 0.9.6.15 UI hotfix"
            content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($body))
        } | ConvertTo-Json -Depth 6
        [IO.File]::WriteAllText($payloadFile, $req, [Text.UTF8Encoding]::new($false))

        try {
            Gh @("api", "--method", "PUT", "repos/$updates/contents/launcher/latest.json",
                "--input", $payloadFile) | Out-Null
        } catch {
            $message = $_.Exception.Message
            if ($attempt -lt 4 -and $message -match '(?i)(HTTP 409|status["\s:]+409|is at [0-9a-f]{40} but expected)') {
                Write-Host "Launcher feed changed concurrently; fetching its current SHA (attempt $attempt of 4)."
                Start-Sleep -Seconds 1
                continue
            }
            throw
        }
        $readback = Feed (Meta "launcher/latest.json")
        if ($readback.latest.version -ne $v -or
            $readback.latest.zipSha256 -ne $ziphash -or
            $readback.latest.launcherSha256 -ne $launcherHash -or
            $readback.latest.updaterSha256 -ne $updaterHash) {
            throw "Launcher manifest readback differs; inspect publication immediately."
        }
        Write-Host "PUBLISHED: ISS26 Academy $v ACTIVE! Start the installed ISS26.exe to update." -ForegroundColor Green
        return
    }
    throw "Concurrent launcher feed changes persisted after four attempts; no unsafe overwrite."
} catch {
    Write-Host ("STOPPED: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host "Log: $logs"
    throw
} finally {
    Stop-Transcript | Out-Null
}
