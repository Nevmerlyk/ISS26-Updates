#requires -Version 5.1
param([string]$Preview,[string]$GameRoot='D:\ISS 26')
$ErrorActionPreference='Stop'
$Pin='7a0d234e3dd3392ee3132e348b7b5c78865ff00d'
$Work=Join-Path $env:LOCALAPPDATA ('ISS26\Test28_'+$Pin.Substring(0,12))
$Names=@('test28_stage3_resources.py','test28_restore_selection_assets.py','test27_build_clean_graphics_recovery.py','test27_build_standalone_atlas_candidate.py','test27_stage_code_audit.py','test27_stage_writer_guard.py','test27_gpu_stream_edit.py','v095_name_lz_codec.py','test27_flag_art_4bpp.py','build_v095_test12_gdc_descriptor_repair.py','build_v094_pointer_repair.py','audit_v095_test10_test11_release_sectors.py','probe_v095_name_gpu_atlas.py','v095_static_prematch_ram_trace.py','build_v095_test25_bosnia_style_isolation.py','test27_extract_real_flag_pixels.py','analyze_flag_test26_unified.py','analyze_flag_test12_phases.py','parse_v095_gpudump.py')
try {
 if(-not $Preview){
    $found=Get-ChildItem -LiteralPath $GameRoot -Filter 'ISS26_Test_0.9.5_TEST27_RecoveryPreview.iss26p' -File -Recurse | Where-Object { Test-Path -LiteralPath (Join-Path $_.DirectoryName 'Test27_Recovery_Build.json') } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if(-not $found){throw 'Test27 preview with its build report not found.'}
    $Preview=$found.FullName
 }
 $Preview=(Get-Item -LiteralPath $Preview).FullName
 $PreviewReport=Join-Path (Split-Path -Parent $Preview) 'Test27_Recovery_Build.json'
 $Track=Get-ChildItem -LiteralPath $GameRoot -Filter 'ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin' -Recurse -File | Select-Object -First 1
 if(-not $Track){throw 'Clean original Track01 not found.'}
 if((Get-FileHash -LiteralPath $Track.FullName -Algorithm SHA256).Hash -ne 'D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44'){throw 'Wrong original Track01.'}
 New-Item -ItemType Directory -Force -Path $Work | Out-Null
 foreach($n in $Names){Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/$Pin/tools/$n" -OutFile (Join-Path $Work $n)}
 $Donors=@(
 @{name='Test25';tag='v0.9.5-bosnia-style-test25';asset='ISS26_0.9.5_BosniaStyle_TEST25.iss26p';sha='85014C8222A408344704CCD8FC192379645E18770876CF4501324D504D55BA67'},
 @{name='Test12';tag='v0.9.5-gdc-descriptor-test12';asset='ISS26_0.9.5_GDC_Descriptor_TEST12.iss26p';sha='7E4FAC687487A3328BB564446DC4835C97D9A5841F335539EA56851F1958C3DD'},
 @{name='Test08';tag='v0.9.6-teamidentity-test08';asset='ISS26_0.9.5_TeamIdentity_BosniaCanada_TEST08.iss26p';sha='E65E5623756643E2DAE7069A66FE888E14439A5A534DBF171BB03630605648B1'})
 $paths=@{}
 foreach($d in $Donors){
   $f=Join-Path $Work $d.asset
   if(-not(Test-Path -LiteralPath $f)){Invoke-WebRequest -UseBasicParsing -Uri ("https://github.com/Nevmerlyk/ISS26-Updates/releases/download/"+$d.tag+"/"+$d.asset) -OutFile $f}
   if((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash -ne $d.sha){throw ('Wrong donor digest: '+$d.name)}
   $paths[$d.name]=$f
 }
 $Python='python';$Prefix=@()
 if(Get-Command py -ErrorAction SilentlyContinue){$Python='py';$Prefix=@('-3')}
 $Dest=Join-Path $GameRoot ('ISS26_Data\diagnostics\Test28_Stage3_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
 New-Item -ItemType Directory -Force -Path $Dest | Out-Null
 $Patch=Join-Path $Dest 'ISS26_Test_0.9.5_TEST28_Stage3.iss26p'
 $Report=Join-Path $Dest 'Test28_Stage3_Build.json'
 $Log=Join-Path $Dest 'Test28_Build.log'
 $exe=Join-Path $Work 'test28_stage3_resources.py'
 Write-Host "Using tested preview: $Preview"
 $ErrorActionPreference='Continue'
 & $Python @Prefix $exe --clean-track $Track.FullName --preview $Preview --preview-report $PreviewReport --test25 $paths.Test25 --test12 $paths.Test12 --test08 $paths.Test08 --output $Patch --report $Report 2>&1 | Tee-Object -FilePath $Log
 $code=$LASTEXITCODE
 $ErrorActionPreference='Stop'
 if($code -ne 0 -or -not(Test-Path -LiteralPath $Patch) -or -not(Test-Path -LiteralPath $Report)){throw "No Test28 patch emitted. Log: $Log"}
 $info=Get-Content -LiteralPath $Report -Raw -Encoding UTF8 | ConvertFrom-Json
 if($info.independent_clean_original_patch -ne $true -or $info.stage3_complete -ne $false -or $info.release_authorized -ne $false -or (Get-FileHash -LiteralPath $Patch -Algorithm SHA256).Hash -ne $info.output_patch_sha256){throw 'Output verification failed'}
 Write-Host "Experimental patch: $Patch" -ForegroundColor Green
 Write-Host "Report: $Report"
 Write-Host 'No installation performed. Stage3 candidate only; see unresolved exceptions in report. No full visual verification.'
} catch {Write-Host $_.Exception.Message -ForegroundColor Red;exit 1}
