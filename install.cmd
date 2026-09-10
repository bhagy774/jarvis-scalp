@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>&1 || (echo Python 3.12 or newer is required. & exit /b 1)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo Dependencies installed. No services or trading processes were started.
echo Read README.md before starting paper mode.
