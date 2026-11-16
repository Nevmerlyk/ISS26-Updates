@echo off
setlocal
set "KITROOT=%~1"
if not defined KITROOT set "KITROOT=D:\ISS 26"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $root=$env:KITROOT; if (!(Test-Path -LiteralPath $root -PathType Container)) { throw 'Game root not found' }; $probe=Join-Path ([IO.Path]::GetTempPath()) ('ISS26-KitProbe-'+[guid]::NewGuid().ToString('N')+'.py'); $out=Join-Path $root ('ISS26_Data\diagnostics\KitResearch_'+[DateTime]::Now.ToString('yyyyMMdd_HHmmss')+'_'+[guid]::NewGuid().ToString('N').Substring(0,6)+'.json'); try { Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/9a1fef79ac550a724e885fcc5084dd00b78ea5aa/tools/kit_resource_probe.py' -OutFile $probe; if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 $probe --root $root --out $out } elseif (Get-Command python -ErrorAction SilentlyContinue) { & python $probe --root $root --out $out } else { throw 'Python 3 is required' }; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Write-Host ('SUCCESS: '+$out) } finally { Remove-Item -LiteralPath $probe -ErrorAction SilentlyContinue }"
exit /b %ERRORLEVEL%
