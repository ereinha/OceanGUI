@echo off
REM Convenience wrapper so users can double-click to install on Windows.
echo Launching PowerShell installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
