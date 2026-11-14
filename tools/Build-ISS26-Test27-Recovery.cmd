@echo off
setlocal EnableExtensions DisableDelayedExpansion
echo Test27 recovery: limited stadium preview; previous graphics may return to the original.
echo The build is experimental and will not install or change your game.
rem Builds only an experimental independent patch. Does not install a game.
set "PIN=a3d972fd78c64756c650f4c8bc13d2ffbf6fbec6"
set "DEST=%TEMP%\ISS26_Test27_Recovery_%PIN%.ps1"
set "URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%PIN%/tools/Build-ISS26-Test27-Recovery.ps1"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $env:URL -OutFile $env:DEST; if(-not ([IO.File]::ReadAllText($env:DEST).Contains('3371b46bc8cd649139b2aab1f4a02f607ae63bc5'))){throw 'Wrong builder source pin'}"
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
