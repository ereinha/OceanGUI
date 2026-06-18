@echo off
REM Launch the Ocean Spectrometer GUI (Windows).
setlocal
set "REPO_ROOT=%~dp0"
if not exist "%REPO_ROOT%.venv\Scripts\python.exe" (
    echo Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)
cd /d "%REPO_ROOT%"
"%REPO_ROOT%.venv\Scripts\pythonw.exe" -m ocean_gui.main
endlocal
