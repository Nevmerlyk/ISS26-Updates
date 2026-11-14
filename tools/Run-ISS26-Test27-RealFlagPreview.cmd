@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem ISS26 Test27 — drag verified old Academy ZIP onto this standalone CMD.
rem The PS1 is pinned to an immutable commit; never uses an old local PS1.
rem This only downloads code and reads the local ZIP; no game data is uploaded.
set "RUNNER_COMMIT=38b69fc4e0b799f0aa23a64a60b4c1d485d3d5d5"
set "TOOL_PIN=7995a5c263ec8641ab5989af5a686cf37ca5de6d"
set "SCRIPT_URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%RUNNER_COMMIT%/tools/Run-ISS26-Test27-RealFlagPreview.ps1"
set "SCRIPT_PATH=%TEMP%\ISS26_Test27_FlagPreview_%RUNNER_COMMIT%.ps1"

echo ISS26 Test27: real Cape Verde/Bosnia flag art and CLUT comparison
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $env:SCRIPT_URL -OutFile $env:SCRIPT_PATH; $script=[IO.File]::ReadAllText($env:SCRIPT_PATH); if(-not $script.Contains($env:TOOL_PIN) -or -not $script.Contains('ExpectedArchiveHash')) {throw 'Pinned helper verification failed'}"
if errorlevel 1 goto error

if "%~1"=="" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%" -Archive "%~1"
)
if errorlevel 1 goto error

echo.
echo PASS: Test27 source/staging comparison opened.
echo Review D:\ISS 26\ISS26_Data\diagnostics\Test27_RealFlagPreview
pause
exit /b 0

:error
echo.
echo ERROR: Test27 preview could not be completed; no BIN/CUE modified.
pause
exit /b 1
