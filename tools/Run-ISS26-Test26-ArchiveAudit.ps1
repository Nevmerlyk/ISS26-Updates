#requires -Version 5.1
<#
ISS26 Test26 — verified, read-only forensic audit of an Academy session ZIP.

Drag the session ZIP onto Run-ISS26-Test26-ArchiveAudit.cmd, or invoke:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-ISS26-Test26-ArchiveAudit.ps1 -Archive "D:\...\report.zip"

No BIN/CUE, game, game saves, update feed or VRAM writes. This runner
downloads 3 public source Python modules from an immutable CI-tested Git commit.
The generated JSON contains only hashes, coordinates and GPU command metadata.
#>
[CmdletBinding()]
param(
  [string]$Archive,
  [string]$GameRoot = 'D:\ISS 26',
  [string]$OutputDir
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Pinned source commit: successful Test26 GitHub Actions run 43609346940.
$Ref = '874adfafde2f47433e379937355efcfefb8defe9'
$ApiRoot = 'https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/'
$Scripts = @(
  'analyze_flag_test12_phases.py',
  'parse_v095_gpudump.py',
  'analyze_flag_test26_unified.py'
)

function Check([bool]$Condition,[string]$Message) {
    if (-not $Condition) { throw $Message }
}

try {
    if ([string]::IsNullOrWhiteSpace($Archive)) {
        $reports = Join-Path $GameRoot 'ISS26_Data\explorer\reports'
        Check (Test-Path -LiteralPath $reports -PathType Container) (
            'No -Archive specified and Academy reports directory does not exist: ' + $reports
        )
        $recent = @(Get-ChildItem -LiteralPath $reports -File -Filter '*.zip' |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1)
        Check ($recent.Count -gt 0) (
            'No Academy report ZIP found. Drag your ZIP onto Run-ISS26-Test26-ArchiveAudit.cmd.'
        )
        $Archive = $recent[0].FullName
    }
    $Archive = [IO.Path]::GetFullPath($Archive)
    Check (Test-Path -LiteralPath $Archive -PathType Leaf) ('ZIP not found: ' + $Archive)
    Check ([IO.Path]::GetExtension($Archive).ToLowerInvariant() -eq '.zip') (
        'Only Academy .zip reports are supported'
    )
    $ArchiveHash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToUpperInvariant()

    if ([string]::IsNullOrWhiteSpace($OutputDir)) {
        # Store reports in a separate folder, never within original PS1 BIN/CUE.
        $OutputDir = Join-Path $GameRoot 'ISS26_Data\diagnostics\Test26'
    }
    $OutputDir = [IO.Path]::GetFullPath($OutputDir)
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    $pythonExe = $null
    $pythonPrefix = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonExe = 'py'
        $pythonPrefix = @('-3')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonExe = 'python'
    }
    Check ($null -ne $pythonExe) 'Python 3.10+ required on this computer.'
    $versionLine = (& $pythonExe @pythonPrefix -c "import sys; print(sys.version_info >= (3, 10))") -join ''
    Check ($LASTEXITCODE -eq 0 -and $versionLine.Trim() -eq 'True') (
        'Python 3.10+ is required for the Test26 analyzer.'
    )

    $scratch = Join-Path ([IO.Path]::GetTempPath()) ('ISS26_Test26_' + $Ref.Substring(0,12))
    New-Item -ItemType Directory -Force -Path $scratch | Out-Null
    foreach ($script in $Scripts) {
        $url = $ApiRoot + $Ref + '/tools/' + $script
        $path = Join-Path $scratch $script
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $path
        Check ((Get-Item -LiteralPath $path).Length -gt 300) (
            'Empty tool download: ' + $script
        )
    }

    $stem = [IO.Path]::GetFileNameWithoutExtension($Archive)
    $output = Join-Path $OutputDir ($stem + '_Test26_Unified.json')
    Write-Host 'ISS26 Test26: read-only unified national flag research' -ForegroundColor Cyan
    Write-Host ('ZIP SHA256: ' + $ArchiveHash)
    Write-Host 'Decoding 72 flag styles, candidate draw CLUT/UV and operator-tagged scenes...'
    & $pythonExe @pythonPrefix (Join-Path $scratch 'analyze_flag_test26_unified.py') $Archive --output $output
    Check ($LASTEXITCODE -eq 0) 'Test26 analyzer failed. The ZIP remains unchanged.'
    Check (Test-Path -LiteralPath $output -PathType Leaf) 'Analyzer did not create JSON'
    $data = Get-Content -LiteralPath $output -Raw -Encoding UTF8 | ConvertFrom-Json
    $meta = [PSCustomObject]@{
        SchemaVersion = 1
        AnalyzerCommit = $Ref
        InputArchiveFile = [IO.Path]::GetFileName($Archive)
        InputArchiveSHA256 = $ArchiveHash
        CreatedUTC = [DateTime]::UtcNow.ToString('o')
        VRAMCaptures = [int]$data.capture_count
        GPUTraces = [int]$data.gpu_trace_count
        DecodedGPUTraces = [int]$data.gpu_trace_decoded_count
        Report = [IO.Path]::GetFileName($output)
        GamePatchChanged = $false
        OriginalBinCueChanged = $false
    }
    $manifest = Join-Path $OutputDir ($stem + '_Test26_AuditManifest.json')
    $meta | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifest -Encoding UTF8
    Write-Host 'PASS: static research report generated' -ForegroundColor Green
    Write-Host ('JSON: ' + $output)
    Write-Host ('Manifest: ' + $manifest)
    Write-Host 'No game patches were modified. For source attribution, share both JSON files.'
}
catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'No game image or update feed was modified.'
    exit 1
}
