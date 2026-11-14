@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PIN=1c1f04a582a3e8bf3ac692240e17194df74cdd7a"
set "DEST=%TEMP%\ISS26_Test29_Bosnia_%PIN%.ps1"
set "URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%PIN%/tools/Build-ISS26-Test29-Bosnia.ps1"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $env:URL -OutFile $env:DEST; if(-not ([IO.File]::ReadAllText($env:DEST).Contains('7d4acb197e8cd4067c960683d7fa98e266cfdb1e'))){throw 'Wrong source pin'}"
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
