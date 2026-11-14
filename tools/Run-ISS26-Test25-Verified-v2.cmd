@echo off
setlocal EnableExtensions
title ISS26 Test25 - verified installer v2
set "GAMEDIR=D:\ISS 26"
if not "%~1"=="" set "GAMEDIR=%~1"
set "INSTALLER=%~dp0Install-ISS26-Test25-Verified-v2.py"
set "INSTALLER_URL=https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/a9fed9cc7fbdd05d6dea17e9594064e5fef43bf6/tools/Install-ISS26-Test25-Verified-v2.py"

echo ISS26 Test25 verified installer v2
echo Original game: "%GAMEDIR%"
echo Downloading pinned installer source from GitHub...
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { Invoke-WebRequest -UseBasicParsing -Uri '%INSTALLER_URL%' -OutFile '%INSTALLER%' } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 goto download_error

where py.exe >nul 2>&1
if not errorlevel 1 (
  py -3 "%INSTALLER%" --game-dir "%GAMEDIR%"
  goto finish
)
where python.exe >nul 2>&1
if not errorlevel 1 (
  python.exe "%INSTALLER%" --game-dir "%GAMEDIR%"
  goto finish
)
echo ERROR: Python 3.10 or newer was not found.
echo Installer was downloaded to: "%INSTALLER%"
goto finish

:download_error
echo ERROR: Could not download pinned installer from GitHub. No game data changed.

:finish
echo.
echo Check the result above. Original BIN/CUE are never modified.
pause
endlocal
