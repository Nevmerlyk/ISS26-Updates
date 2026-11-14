@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Test27 temporary visual replacement; no disc/patch/BIOS/save writes.
rem Requires paused PCSX-Redux, exact Cape home / Bosnia away Test25 state,
rem existing local web server, Python 3.10+, and explicit Y confirmation.
rem The PCSX-Redux HTTP server may bind all interfaces: isolate it first.
set "ISS26_PIN=c7f45e94402526b4189f9f2fab9e823c16793532"
set "ISS26_WORK=%LOCALAPPDATA%\ISS26\Test27LiveFlagPreview"
echo Test27 - temporary VRAM preview; no BIN/CUE patch.
echo Pause PCSX-Redux at the Cape Verde - Bosnia prematch banner.
echo Enable the emulator web server only on a trusted isolated connection.
echo This client contacts 127.0.0.1:8080 only. Disable the server afterwards.
echo.
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 goto nopy
  set "PYTHON=python"
  set "PYARGS="
) else (
  set "PYTHON=py"
  set "PYARGS=-3"
)
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path $env:ISS26_WORK | Out-Null; foreach($f in @('test27_live_flag_replacement.py','test27_flag_art_4bpp.py')) { $u='https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/'+$env:ISS26_PIN+'/tools/'+$f; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile (Join-Path $env:ISS26_WORK $f) }"
if errorlevel 1 goto failed
"%PYTHON%" %PYARGS% "%ISS26_WORK%\test27_live_flag_replacement.py" --check
if errorlevel 1 goto mismatch
echo.
echo Exact match verified. This preview changes 2 staging tiles and 2 CLUTs.
echo Other objects using the same CLUT may also change. Keep emulator paused.
choice /C YN /N /M "Apply the temporary VRAM replacement? [Y/N] "
if errorlevel 2 goto declined
if not "%ERRORLEVEL%"=="1" goto failed
set "BACKUP=%ISS26_WORK%\Test27_LiveFlagRollback_%RANDOM%_%RANDOM%.json"
"%PYTHON%" %PYARGS% "%ISS26_WORK%\test27_live_flag_replacement.py" --apply --backup "%BACKUP%"
if errorlevel 1 goto failed
echo.
echo PASS: GPU readback matched expected VRAM; resume and inspect both flags.
echo Restart Test Game without saving a state to discard the preview.
echo Backup: "%BACKUP%"
echo Optional rollback while paused and matching:
echo "%PYTHON%" %PYARGS% "%ISS26_WORK%\test27_live_flag_replacement.py" --restore --backup "%BACKUP%"
pause
exit /b 0

:nopy
echo Python 3.10 or later is required.
goto failed

:mismatch
echo No replacement attempted. Wrong frame, incompatible server, or unverified match.
goto enderror

:declined
echo Cancelled before any VRAM write.
pause
exit /b 0

:failed
echo Test27 preview did not finish successfully.
echo If a write was attempted, read the Python rollback result above.
echo Restart the emulator without saving state if recovery is uncertain.
:enderror
pause
exit /b 1
