@echo off
setlocal EnableExtensions DisableDelayedExpansion
echo Test27 recovery: some previous graphics may return to the original.
echo The build is experimental and will not install or change your game.
rem Builds only an experimental independent patch. Does not install a game.
set "PIN=73b5bfe46b7e1ba912c3ce4200725c83a3e9ee8d"
set "DEST=%TEMP%\ISS26_Test27_Recovery_%PIN%.ps1"
set "URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%PIN%/tools/Build-ISS26-Test27-Recovery.ps1"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $env:URL -OutFile $env:DEST; if(-not ([IO.File]::ReadAllText($env:DEST).Contains('1f9a00a2d113db746993fcabe09dcc27a6bcdc5e'))){throw 'Wrong builder source pin'}"
if errorlevel 1 goto failed
if "%~1"=="" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEST%"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%DEST%" -Archive "%~1"
)
if errorlevel 1 goto failed
echo.
echo Local experimental recovery candidate created, not installed.
pause
exit /b 0
:failed
echo.
echo Builder stopped. No game files or update channels modified.
pause
exit /b 1
