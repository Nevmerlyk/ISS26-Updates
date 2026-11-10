@echo off
setlocal EnableExtensions
title ISS26 v0.9.5 Independent Flag Builder
set "GAMEROOT=%~dp0..\..\..\..\"
set "TRACK=%GAMEROOT%ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin"
set "PLAN=%GAMEROOT%verified-flag-plan.json"
if not exist "%TRACK%" (
  echo ERROR: clean EU Track 01 was not found next to the project.
  echo Run with explicit paths:
  echo   py -3 "%~dp0build_v095.py" --original "Path\Track 01.bin" --plan "Path\verified-flag-plan.json"
  pause
  exit /b 2
)
if not exist "%PLAN%" (
  echo ERROR: verified-flag-plan.json is missing.
  echo The builder will not invent GPU/CLUT locations or release a broken patch.
  echo Provide a plan validated against the real game first.
  pause
  exit /b 2
)
py -3 "%~dp0build_v095.py" --original "%TRACK%" --plan "%PLAN%" --output "%GAMEROOT%ISS26_0.9.5_flags_only.iss26p"
if errorlevel 1 (
  echo FAILED: No patch was promoted. Original game unchanged.
  pause
  exit /b 2
)
echo Candidate build complete. Verify all flag screens in PCSX-Redux before Stable.
pause
