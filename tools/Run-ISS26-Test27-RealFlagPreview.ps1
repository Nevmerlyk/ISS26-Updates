#requires -Version 5.1
<#
ISS26 Test27 - owner-local real source/staging flag visual comparison.
READ-ONLY: consumes existing private Academy ZIP, downloads source-only
research scripts pinned to CI-green commit. NEVER reads/changes original game
BIN/CUE, patch feeds or memory cards. Does not upload screenshots or ROM.
#>
[CmdletBinding()]
param(
    [string]$Archive,
    [string]$GameRoot = "D:\ISS 26",
    [string]$OutputDirectory = "",
    [switch]$NoOpen
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Pin = '7995a5c263ec8641ab5989af5a686cf37ca5de6d'
$ExpectedArchiveHash = '611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690'
$ScriptNames = @(
    'test27_extract_real_flag_pixels.py',
    'test27_flag_art_4bpp.py',
    'analyze_flag_test12_phases.py',
    'analyze_flag_test26_unified.py',
    'parse_v095_gpudump.py'
)
function Require([bool]$condition, [string]$message) {
    if (-not $condition) { throw $message }
}
try {
    if ([string]::IsNullOrWhiteSpace($Archive)) {
        $name = '20261114_154539_315b0c.zip'
        $places = @(
            (Join-Path $GameRoot 'ISS26_Data\explorer\reports'),
            (Join-Path $GameRoot 'ISS26_Data'),
            $GameRoot
        )
        $found = @($places | ForEach-Object {
            if (Test-Path -LiteralPath $_ -PathType Container) {
                Join-Path $_ $name
            }
        } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -Unique)
        Require ($found.Count -gt 0) (
            'Academy ZIP not found in usual folders. Drag 20261114_154539_315b0c.zip onto the CMD.'
        )
        $Archive = $found[0]
    }
    $Archive = [IO.Path]::GetFullPath($Archive)
    Require (Test-Path -LiteralPath $Archive -PathType Leaf) ("Archive missing: " + $Archive)
    Require ([IO.Path]::GetExtension($Archive).ToLowerInvariant() -eq '.zip') 'Expected existing Academy ZIP'
    $ActualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToUpperInvariant()
    Require ($ActualHash -eq $ExpectedArchiveHash) (
        'This is NOT the verified Test26 archive; refusing to process unrelated screenshots.'
    )
    if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
        $OutputDirectory = Join-Path $GameRoot 'ISS26_Data\diagnostics\Test27_RealFlagPreview'
    }
    $OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $Python = $null
    $Prefix = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = 'py'
        $Prefix = @('-3')
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $Python = 'python'
    }
    Require ($null -ne $Python) 'Python 3.10+ is required.'
    $Version = (& $Python @Prefix -c 'import sys; print(sys.version_info >= (3,10))') -join ''
    Require ($LASTEXITCODE -eq 0 -and $Version.Trim() -eq 'True') 'Python 3.10+ is required.'
    $Work = Join-Path ([IO.Path]::GetTempPath()) ('ISS26_Test27_FlagAudit_' + $Pin.Substring(0,12))
    New-Item -ItemType Directory -Force -Path $Work | Out-Null
    foreach ($item in $ScriptNames) {
        $url = 'https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/' + $Pin + '/tools/' + $item
        $local = Join-Path $Work $item
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $local
        Require ((Get-Item -LiteralPath $local).Length -gt 200) ('Missing pinned tool: ' + $item)
    }
    Write-Host 'ISS26 Test27: actual VRAM art, live CLUT and 12-row mask' -ForegroundColor Cyan
    Write-Host ('Source archive SHA256 verified: ' + $ActualHash)
    & $Python @Prefix (Join-Path $Work 'test27_extract_real_flag_pixels.py') --academy-zip $Archive --output-dir $OutputDirectory
    Require ($LASTEXITCODE -eq 0) 'Actual VRAM art extractor failed'
    $Sheet = Join-Path $OutputDirectory 'Test27_Flag_Source_vs_Stage_Comparison.png'
    $Json = Join-Path $OutputDirectory 'test27_real_flag_pixels.json'
    Require ((Test-Path -LiteralPath $Sheet -PathType Leaf) -and
        (Test-Path -LiteralPath $Json -PathType Leaf)) 'No real comparison image or JSON was produced'
    $Picture = [IO.File]::ReadAllBytes($Sheet)
    Require ($Picture.Length -gt 100) 'Generated comparison image is empty'
    $Signature = @(137,80,78,71,13,10,26,10)
    for ($i=0; $i -lt $Signature.Count; $i++) {
        Require ($Picture[$i] -eq $Signature[$i]) 'Generated image is not PNG'
    }
    $Metadata = Get-Content -Raw -LiteralPath $Json -Encoding UTF8 | ConvertFrom-Json
    Require ($Metadata.input_zip_sha256 -eq $ExpectedArchiveHash) 'Unexpected PNG provenance'
    Require ($Metadata.source_disc_modified -eq $false -and
             $Metadata.game_patch_built -eq $false) 'Unsafe preview metadata'
    Require ($Metadata.comparison_sheet_file -eq [IO.Path]::GetFileName($Sheet)) 'Wrong image report'
    Write-Host 'PASS: 11 PNG previews and 1 JSON; original disc untouched' -ForegroundColor Green
    Write-Host ('Comparison image: ' + $Sheet)
    Write-Host ('Metadata: ' + $Json)
    Write-Host 'Top row Cape Verde; bottom row Bosnia. Columns: source CLUT / stage zero-marked / index delta.'
    if (-not $NoOpen) { Start-Process -FilePath $Sheet }
}
catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'The game BIN/CUE, patches and memory cards were not changed.'
    exit 1
}
