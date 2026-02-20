@echo off
REM Open the agent CLI in its own CMD window.
cd /d "%~dp0"
start "Agent CLI" cmd /k "cd /d "%~dp0" && python cli.py %*"
exit /b 0
