# JARVIS HUD Launcher
# Run this to open the live 3D dashboard in your browser

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║     JARVIS AI TRADING COMMAND CENTER    ║" -ForegroundColor Cyan
Write-Host "  ║           HUD Server Launcher           ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Starting HUD Server on http://localhost:7788" -ForegroundColor Green
Write-Host "  Opening dashboard in browser..." -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Start browser after 2 seconds
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:7788"
} | Out-Null

# Start the HUD server
Set-Location "c:\jarvis"
python jarvis_hud_server.py
