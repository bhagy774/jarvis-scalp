# Quant Systems Environment Setup Script
# Target: Windows PowerShell

Write-Host "Creating virtual environment 'jenv'..." -ForegroundColor Cyan
py -m venv jenv

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
# Temporarily set ExecutionPolicy for the current PowerShell session to allow running the activation script
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
& .\jenv\Scripts\Activate.ps1

Write-Host "Upgrading pip..." -ForegroundColor Cyan
py -m pip install --upgrade pip

Write-Host "Installing core algorithmic trading dependencies..." -ForegroundColor Cyan
pip install websockets pandas colorama requests python-dotenv numpy scipy scikit-learn psutil

Write-Host "Installing CUDA 12.1 PyTorch for GTX 1650 GPU..." -ForegroundColor Cyan
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

Write-Host "Environment setup complete and active!" -ForegroundColor Green
