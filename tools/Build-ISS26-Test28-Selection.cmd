@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PIN=32520b64b3101df8f8cda3a007febbec3cb129c5"
set "DEST=%TEMP%\ISS26_Test28_Selection_%PIN%.ps1"
set "URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%PIN%/tools/Build-ISS26-Test28-Selection.ps1"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $env:URL -OutFile $env:DEST; if(-not ([IO.File]::ReadAllText($env:DEST).Contains('3cabb8baad9806c4e782fa8310ad6e7db38a2221'))){throw 'Wrong source pin'}"
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
