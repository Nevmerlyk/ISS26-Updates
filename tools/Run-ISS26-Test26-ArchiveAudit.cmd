@echo off
setlocal
rem ISS26 Test26 - drag and drop your Academy report ZIP onto this CMD file.
rem No original game files, patches or saves are modified.
cd /d "%~dp0"
if "%~1"=="" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-ISS26-Test26-ArchiveAudit.ps1"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-ISS26-Test26-ArchiveAudit.ps1" -Archive "%~1"
)
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" echo Test26 analysis failed. Please copy the ERROR line above.
if "%EXITCODE%"=="0" echo Test26 analysis completed. The output JSON is under D:\ISS 26\ISS26_Data\diagnostics\Test26.
pause
exit /b %EXITCODE%
