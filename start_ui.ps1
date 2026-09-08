# JARVIS UI Launcher

Write-Host "Starting JARVIS UI..."

Write-Host "Starting Python Server..."
Set-Location c:\jarvis
Start-Process -NoNewWindow python -ArgumentList jarvis_hud_server.py

Start-Sleep -Seconds 2

Write-Host "Starting React App..."
Set-Location c:\jarvis\jarvis_web
Start-Process http://localhost:5173
npm run dev
