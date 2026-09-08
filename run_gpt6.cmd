@echo off
chcp 65001 >nul
cd /d "C:\jarvis"
if "%~1"=="" (
    .\jenv\Scripts\python.exe kie_gpt6_client.py
) else (
    .\jenv\Scripts\python.exe kie_gpt6_client.py %*
)
pause
