param([switch]$StartPaper)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $StartPaper) { throw 'Refusing to start. Use -StartPaper for intentional paper monitoring.' }
foreach ($flag in @('JARVIS_AUTO_TRADE', 'JARVIS_LIVE_EXECUTION', 'DELTA_ORDER_EXECUTION_ENABLED')) {
    if ([Environment]::GetEnvironmentVariable($flag) -eq 'true') { throw "Disable $flag before paper startup." }
}
$env:JARVIS_START_PAPER = '1'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run install.cmd first.' }
# Deliberately do not automatically restart a process that may need reconciliation.
& $python (Join-Path $PSScriptRoot 'jarvis_FIXED.py')
exit $LASTEXITCODE
