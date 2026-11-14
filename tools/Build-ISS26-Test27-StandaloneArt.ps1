#requires -Version 5.1
<#
ISS26 Test27 experimental standalone art builder, LOCAL and OFFLINE DISC.
Downloads public source and official Test25 .iss26p; original Track01 and
owner Academy ZIP are read only. Never installs a patch, uploads the game
or touches the game's live update feeds. Can refuse on real source evidence.
#>
[CmdletBinding()]
param(
    [string]$Archive,
    [string]$OriginalTrack,
    [string]$Test25,
    [string]$GameRoot = "D:\ISS 26"
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Pin='e2217f7c7d325baae437d9abf408ffdc71ad9a6c'
$Work=Join-Path $env:LOCALAPPDATA ('ISS26\Test27StandaloneArt_'+$Pin.Substring(0,12))
$Names=@(
 'test27_build_standalone_atlas_candidate.py',
 'test27_gpu_stream_edit.py',
 'v095_name_lz_codec.py',
 'test27_flag_art_4bpp.py',
 'build_v095_test12_gdc_descriptor_repair.py',
 'build_v094_pointer_repair.py',
 'audit_v095_test10_test11_release_sectors.py',
 'probe_v095_name_gpu_atlas.py',
 'v095_static_prematch_ram_trace.py',
 'build_v095_test25_bosnia_style_isolation.py',
 'test27_extract_real_flag_pixels.py',
 'analyze_flag_test26_unified.py',
 'analyze_flag_test12_phases.py',
 'parse_v095_gpudump.py'
)
function Find-Exact([string]$name) {
    $candidates=@(
        (Join-Path $GameRoot $name),
        (Join-Path $GameRoot ('ISS26_Data\explorer\reports\'+$name)),
        (Join-Path $GameRoot ('ISS26_Data\'+$name)),
        (Join-Path $GameRoot ('Original\'+$name))
    )
    foreach ($p in $candidates) {
        if(Test-Path -LiteralPath $p -PathType Leaf){return $p}
    }
    $item=Get-ChildItem -LiteralPath $GameRoot -Filter $name -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if($item){return $item.FullName}
    return $null
}
function Need-File($p,[string]$label) {
    if([string]::IsNullOrWhiteSpace($p) -or -not(Test-Path -LiteralPath $p -PathType Leaf)){
        throw ("Missing "+$label+"; specify its path explicitly.")
    }
    return (Get-Item -LiteralPath $p).FullName
}
try {
    if(-not(Test-Path -LiteralPath $GameRoot -PathType Container)){throw "GameRoot not found: $GameRoot"}
    if(-not $Archive){$Archive=Find-Exact '20261114_154539_315b0c.zip'}
    if(-not $OriginalTrack){$OriginalTrack=Find-Exact 'ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin'}
    $Archive=Need-File $Archive 'original Test26 Academy ZIP'
    $OriginalTrack=Need-File $OriginalTrack 'clean original Track01'
    $shaTrack=(Get-FileHash -LiteralPath $OriginalTrack -Algorithm SHA256).Hash
    if($shaTrack -ne 'D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44'){throw 'Wrong original Track01; no writes.'}
    $shaArchive=(Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
    if($shaArchive -ne '611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690'){throw 'Wrong Academy archive; no writes.'}
    New-Item -ItemType Directory -Force -Path $Work | Out-Null
    if(-not $Test25){
        $Test25=Join-Path $Work 'ISS26_0.9.5_BosniaStyle_TEST25.iss26p'
        if(-not(Test-Path -LiteralPath $Test25 -PathType Leaf)){
            Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/Nevmerlyk/ISS26-Updates/releases/download/v0.9.5-bosnia-style-test25/ISS26_0.9.5_BosniaStyle_TEST25.iss26p' -OutFile $Test25
        }
    }
    $Test25=Need-File $Test25 'official Test25 patch'
    if((Get-FileHash -LiteralPath $Test25 -Algorithm SHA256).Hash -ne '85014C8222A408344704CCD8FC192379645E18770876CF4501324D504D55BA67'){
        throw 'Test25 SHA mismatch; no writes to game.'
    }
    $Python='python'
    $Prefix=@()
    if(Get-Command py -ErrorAction SilentlyContinue){$Python='py';$Prefix=@('-3')}
    elseif(-not(Get-Command python -ErrorAction SilentlyContinue)){throw 'Install Python 3.10+ first.'}
    $ver=(& $Python @Prefix -c 'import sys; print(sys.version_info >= (3,10))') -join ''
    if($LASTEXITCODE -ne 0 -or $ver.Trim() -ne 'True'){throw 'Python 3.10+ required.'}
    foreach($n in $Names){
        $uri="https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/$Pin/tools/$n"
        Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile (Join-Path $Work $n)
    }
    $Dest=Join-Path $GameRoot ('ISS26_Data\diagnostics\Test27_StandaloneArt_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
    New-Item -ItemType Directory -Path $Dest | Out-Null
    $Patch=Join-Path $Dest 'ISS26_Test_0.9.5_TEST27_SourceArt.iss26p'
    $Report=Join-Path $Dest 'Test27_StandaloneArt_Build.json'
    Write-Host 'Building a source-art-only candidate. It may fail closed on real CLUT/resource conflicts.' -ForegroundColor Cyan
    Write-Host 'No game installation, no update promotion, no original-disc changes.'
    $Log=Join-Path $Dest 'Test27_Build.log'
    $exe=Join-Path $Work 'test27_build_standalone_atlas_candidate.py'
    $ErrorActionPreference='Continue'
    & $Python @Prefix $exe --clean-track $OriginalTrack --test25 $Test25 --academy-zip $Archive --output $Patch --report $Report --experimental 2>&1 | Tee-Object -FilePath $Log
    $code=$LASTEXITCODE
    $ErrorActionPreference='Stop'
    if($code -ne 0 -or -not(Test-Path -LiteralPath $Patch -PathType Leaf) -or -not(Test-Path -LiteralPath $Report -PathType Leaf)){
        Write-Host "BLOCKED: no usable candidate. Send only the build log: $Log" -ForegroundColor Yellow
        exit 1
    }
    $info=Get-Content -LiteralPath $Report -Raw -Encoding UTF8 | ConvertFrom-Json
    if($info.release_authorized -ne $false -or $info.runtime_stage_writer_fixed -ne $false -or
        $info.test25_required_at_install -ne $false -or
        (Get-FileHash -LiteralPath $Patch -Algorithm SHA256).Hash -ne $info.output_patch_sha256){
        throw 'Output metadata or patch digest verification failed. Do not use candidate.'
    }
    Write-Host "EXPERIMENTAL standalone source-art patch built: $Patch" -ForegroundColor Green
    Write-Host "Report: $Report"
    Write-Host 'Bosnia runtime clipping, bonus-team ownership, and gameplay acceptance are not fixed or verified.'
    Write-Host 'No patch installed. Do not publish as stable.'
} catch {
    Write-Host ("ERROR: "+$_.Exception.Message) -ForegroundColor Red
    Write-Host 'No original disc or game update feed modified.'
    exit 1
}
