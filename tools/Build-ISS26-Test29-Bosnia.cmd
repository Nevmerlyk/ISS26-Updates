@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PIN=afabfef4484207856046d838a59f186d0116ccd1"
set "DEST=%TEMP%\ISS26_Test29_Bosnia_%PIN%.ps1"
set "URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%PIN%/tools/Build-ISS26-Test29-Bosnia.ps1"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $env:URL -OutFile $env:DEST; if(-not ([IO.File]::ReadAllText($env:DEST).Contains('fe6f214c5c86748b5224343a9596787844015b4d'))){throw 'Wrong source pin'}"
if errorlevel 1 goto failed
if "%~1"=="" (
 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEST%"
) else (
 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEST%" -Preview "%~1"
)
if errorlevel 1 goto failed
echo Test29 candidate built; NOT installed.
pause
exit /b 0
:failed
echo Test29 stopped. Please retain the build log.
pause
exit /b 1
