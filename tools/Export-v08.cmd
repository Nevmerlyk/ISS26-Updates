@echo off
setlocal
title ISS26 v0.8 to Launcher patch
echo ISS26 v0.8: export ONLY modified Track 01 data for ISS26 Updates.
echo The full game and audio tracks are NOT uploaded.
echo.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0export_v08_track01.py" %*
  goto :done
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%~dp0export_v08_track01.py" %*
  goto :done
)
echo Python 3 is required. Install it from https://www.python.org/downloads/windows/
:done
echo.
pause
