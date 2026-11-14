#requires -Version 5.1
param([string]$Preview,[string]$GameRoot='D:\ISS 26')
$ErrorActionPreference='Stop'
$Pin='fe6f214c5c86748b5224343a9596787844015b4d'
$Work=Join-Path $env:LOCALAPPDATA ('ISS26\Test29_'+$Pin.Substring(0,12))
$Names=@('test29_bosnia_single_block.py','test28_stage3_resources.py','test28_restore_selection_assets.py','test27_build_clean_graphics_recovery.py','test27_build_standalone_atlas_candidate.py','test27_stage_code_audit.py','test27_stage_writer_guard.py','test27_gpu_stream_edit.py','v095_name_lz_codec.py','test27_flag_art_4bpp.py','build_v095_test12_gdc_descriptor_repair.py','build_v094_pointer_repair.py','audit_v095_test10_test11_release_sectors.py','probe_v095_name_gpu_atlas.py','v095_static_prematch_ram_trace.py','build_v095_test25_bosnia_style_isolation.py','test27_extract_real_flag_pixels.py','analyze_flag_test26_unified.py','analyze_flag_test12_phases.py','parse_v095_gpudump.py')
try {
 if(-not $Preview){
    $found=Get-ChildItem -LiteralPath $GameRoot -Filter 'ISS26_Test_0.9.5_TEST28_Stage3.iss26p' -File -Recurse | Where-Object { Test-Path -LiteralPath (Join-Path $_.DirectoryName 'Test28_Stage3_Build.json') } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if(-not $found){throw 'Test28 Stage3 patch with its build report not found.'}
    $Preview=$found.FullName
 }
 $Preview=(Get-Item -LiteralPath $Preview).FullName
 $PreviewReport=Join-Path (Split-Path -Parent $Preview) 'Test28_Stage3_Build.json'
 $Track=Get-ChildItem -LiteralPath $GameRoot -Filter 'ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin' -Recurse -File | Select-Object -First 1
 if(-not $Track){throw 'Clean original Track01 not found.'}
 if((Get-FileHash -LiteralPath $Track.FullName -Algorithm SHA256).Hash -ne 'D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44'){throw 'Wrong original Track01.'}
 New-Item -ItemType Directory -Force -Path $Work | Out-Null
 foreach($n in $Names){Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/$Pin/tools/$n" -OutFile (Join-Path $Work $n)}
 $Python='python';$Prefix=@()
 if(Get-Command py -ErrorAction SilentlyContinue){$Python='py';$Prefix=@('-3')}
 $Dest=Join-Path $GameRoot ('ISS26_Data\diagnostics\Test29_Bosnia_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
 New-Item -ItemType Directory -Force -Path $Dest | Out-Null
 $Patch=Join-Path $Dest 'ISS26_Test_0.9.5_TEST29_Bosnia.iss26p'
 $Report=Join-Path $Dest 'Test29_Bosnia_Build.json'
 $Log=Join-Path $Dest 'Test29_Build.log'
 $exe=Join-Path $Work 'test29_bosnia_single_block.py'
 Write-Host "Using tested preview: $Preview"
 $ErrorActionPreference='Continue'
 & $Python @Prefix $exe --clean-track $Track.FullName --test28 $Preview --test28-report $PreviewReport --output $Patch --report $Report 2>&1 | Tee-Object -FilePath $Log
 $code=$LASTEXITCODE
 $ErrorActionPreference='Stop'
 if($code -ne 0 -or -not(Test-Path -LiteralPath $Patch) -or -not(Test-Path -LiteralPath $Report)){throw "No Test29 patch emitted. Log: $Log"}
 $info=Get-Content -LiteralPath $Report -Raw -Encoding UTF8 | ConvertFrom-Json
 if($info.independent_clean_original_patch -ne $true -or $info.runtime_crop_fixed -ne $false -or $info.release_authorized -ne $false -or (Get-FileHash -LiteralPath $Patch -Algorithm SHA256).Hash -ne $info.output_patch_sha256){throw 'Output verification failed'}
 Write-Host "Experimental patch: $Patch" -ForegroundColor Green
 Write-Host "Report: $Report"
 Write-Host 'No installation performed. Test29 is an experimental relocation; runtime clipping and bonus-team ownership are unverified.'
} catch {Write-Host $_.Exception.Message -ForegroundColor Red;exit 1}
