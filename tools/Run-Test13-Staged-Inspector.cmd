@echo off
setlocal
cd /d "%~dp0"
set "GAMEROOT=D:\ISS 26"
if not exist "%GAMEROOT%\ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin" (
  set "GAMEROOT=%~dp0"
)
if not exist "%GAMEROOT%\ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin" (
  echo The clean European Track 01 is missing.
  echo Place the original game in D:\ISS 26 or alongside this .cmd file.
  pause
  exit /b 1
)
set "TRACK=%GAMEROOT%\ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin"
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 inspect_v095_test13_from_stage.py --clean-track "%TRACK%" --outdir "ISS26_Test13_NameAnalysis"
) else (
  python inspect_v095_test13_from_stage.py --clean-track "%TRACK%" --outdir "ISS26_Test13_NameAnalysis"
)
if %ERRORLEVEL% neq 0 (
  echo ERROR: Verification failed. Original Track 01 remains unchanged.
) else (
  echo SUCCESS: Verified 84 original sectors and the three Test13 name atlases.
  echo See the PNG and JSON files in ISS26_Test13_NameAnalysis.
)
pause
