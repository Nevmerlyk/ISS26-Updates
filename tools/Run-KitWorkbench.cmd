@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-KitWorkbench.ps1" %*
if errorlevel 1 echo STOP: Audit did not finish. Original game is unchanged.
pause
