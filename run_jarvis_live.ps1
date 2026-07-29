param(
    [string]$ScriptToRun = "jarvis_FIXED.py",
    [int]$RestartDelaySeconds = 5
)

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "🚀 JARVIS LIVE MONITORING & AUTO-RESTART SYSTEM 🚀" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "Monitoring File: $ScriptToRun" -ForegroundColor Yellow

$crashCount = 0

while ($true) {
    Write-Host "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting Jarvis..." -ForegroundColor Green
    
    # Run the Python script
    try {
        # Using python directly as virtual env should be activated
        $process = Start-Process -FilePath "python" -ArgumentList $ScriptToRun -NoNewWindow -Wait -PassThru
        
        $exitCode = $process.ExitCode
        
        if ($exitCode -eq 0) {
            Write-Host "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Jarvis stopped normally (Exit Code 0). Exiting monitor." -ForegroundColor Yellow
            break
        } else {
            $crashCount++
            Write-Host "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ⚠️ CRASH DETECTED! (Exit Code $exitCode)" -ForegroundColor Red
            Write-Host "Total Crashes so far: $crashCount" -ForegroundColor Red
            Write-Host "Restarting in $RestartDelaySeconds seconds... Press Ctrl+C to stop completely." -ForegroundColor Yellow
            
            Start-Sleep -Seconds $RestartDelaySeconds
        }
    } catch {
        Write-Host "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ❌ FATAL ERROR: Failed to execute Python. Check your environment." -ForegroundColor Red
        break
    }
}
