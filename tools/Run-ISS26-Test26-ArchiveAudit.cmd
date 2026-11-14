@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem ISS26 Test26 single-file, read-only Academy ZIP forensic runner.
rem No adjacent PS1 is needed: always fetch CI-verified PS1 from pinned Git commit.
rem No BIN/CUE, game patches, original disc, saves, or stable feed are modified.
set "RUNNER_COMMIT=5eb998343617e4dc413330a759d157490e6cb95c"
set "ANALYZER_COMMIT=60b22eaae21d8a738455e4a4695c1447ed981ef6"
set "RUNNER_URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/%RUNNER_COMMIT%/tools/Run-ISS26-Test26-ArchiveAudit.ps1"
set "RUNNER_FILE=%TEMP%\ISS26_Test26_ArchiveAudit_%RUNNER_COMMIT%.ps1"

echo ISS26 Test26 - verified zero-mask audit (one-file runner)
echo Expected analyzer: %ANALYZER_COMMIT%
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $u=$env:RUNNER_URL; $p=$env:RUNNER_FILE; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; $s=[IO.File]::ReadAllText($p); if (-not $s.Contains($env:ANALYZER_COMMIT)) {throw 'Downloaded runner pins wrong analyzer'}; if (-not $s.Contains('STALE ANALYZER')) {throw 'Downloaded runner lacks stale-report protection'}"
if errorlevel 1 goto download_failed

if "%~1"=="" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%RUNNER_FILE%"
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%RUNNER_FILE%" -Archive "%~1"
)
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" (
    echo ERROR: Test26 analysis failed. See the error above.
) else (
    echo SUCCESS: verified new Test26 zero-mask report created.
    echo Output: D:\ISS 26\ISS26_Data\diagnostics\Test26
    echo The Compact JSON must contain reference_mask_audits.
)
pause
exit /b %EXITCODE%

:download_failed
echo.
echo ERROR: Could not download or validate pinned Test26 PowerShell runner.
echo No game, original BIN/CUE or patch files were changed.
pause
exit /b 1
