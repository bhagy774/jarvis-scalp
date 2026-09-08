#!/bin/bash

echo "🚀 Starting JARVIS Server Setup..."

# 1. Update and install dependencies
echo "📦 Installing system dependencies..."
apt-get update && apt-get install -y python3 python3-pip git nano zstd

# 2. Clone the repo
echo "📥 Cloning JARVIS repository..."
git clone https://github.com/bhagy774/jarvis-scalp.git
cd jarvis-scalp || exit

# 3. Install Python requirements
echo "🐍 Installing Python packages..."
pip install -r requirements.txt --break-system-packages

# 4. Install Ollama
echo "🦙 Installing Ollama (AI Engine)..."
curl -fsSL https://ollama.com/install.sh | sh

# 5. Start Ollama server in the background
echo "🧠 Starting Ollama server in background..."
ollama serve > ollama.log 2>&1 &
sleep 5 # Give Ollama a few seconds to boot up

# 6. Download AI Models
echo "📥 Downloading AI Models (This will take some time)..."
ollama pull deepseek-r1:14b
ollama pull qwen2.5:14b
ollama pull mistral-nemo:12b

# 7. Configure Environment Variables
echo "⚙️ Opening .env file for you to configure..."
touch .env
nano .env

# 8. Start JARVIS
echo "🔥 Starting JARVIS Trading System..."
python3 jarvis_FIXED.py
