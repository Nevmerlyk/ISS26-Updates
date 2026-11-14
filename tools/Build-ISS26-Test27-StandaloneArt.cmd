@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Builds only an experimental independent patch. Does not install a game.
set "PIN=7a9c22b8ff0416ddcf3ddb773b2614ce72b4f3c7"
set "DEST=%TEMP%\ISS26_Test27_StandaloneArt_%PIN%.ps1"
set "URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%PIN%/tools/Build-ISS26-Test27-StandaloneArt.ps1"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $env:URL -OutFile $env:DEST; if(-not ([IO.File]::ReadAllText($env:DEST).Contains('33a6c27ad794889b6adfac72dcb1d8852f634210'))){throw 'Wrong builder source pin'}"
if errorlevel 1 goto failed
if "%~1"=="" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEST%"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEST%" -Archive "%~1"
)
if errorlevel 1 goto failed
echo.
echo Local experimental candidate created, not installed.
pause
exit /b 0
:failed
echo.
echo Builder stopped. No game files or update channels modified.
pause
exit /b 1
