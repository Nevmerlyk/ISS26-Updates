@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PIN=98d38eefd2e6aded9b89a546d25807d0ecd64da6"
set "DEST=%TEMP%\ISS26_Test28_Stage3_%PIN%.ps1"
set "URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%PIN%/tools/Build-ISS26-Test28-Stage3.ps1"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $env:URL -OutFile $env:DEST; if(-not ([IO.File]::ReadAllText($env:DEST).Contains('7a0d234e3dd3392ee3132e348b7b5c78865ff00d'))){throw 'Wrong source pin'}"
if errorlevel 1 goto failed
if "%~1"=="" (
 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEST%"
) else (
 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEST%" -Preview "%~1"
)
if errorlevel 1 goto failed
echo Test28 candidate built; NOT installed.
pause
exit /b 0
:failed
echo Test28 stopped. Please retain the build log.
pause
exit /b 1
