#!/usr/bin/env bash
# ============================================================
# JARVIS Cloud GPU Setup Script (Ubuntu 22.04 / RunPod / VPS)
# Run:  bash cloud_setup.sh
# Safe: Paper mode default. Koi live trading nahi.
# ============================================================
set -e

echo "=============================================="
echo "  JARVIS Cloud GPU Setup - Starting"
echo "=============================================="

# ---------- 1. System packages ----------
echo "[1/7] System packages install thay chhe..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git curl tmux htop \
    build-essential software-properties-common

# ---------- 2. Node.js 20 (dashboard mate) ----------
echo "[2/7] Node.js install thay chhe..."
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

# ---------- 3. Ollama (local AI brain) ----------
echo "[3/7] Ollama install thay chhe..."
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
# Ollama service background ma start
if ! pgrep -x ollama >/dev/null 2>&1; then
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  sleep 5
fi

# ---------- 4. Repo clone/update ----------
echo "[4/7] Repo clone/update thay chhe..."
if [ ! -d "$HOME/jarvis-scalp" ]; then
  git clone https://github.com/bhagy774/jarvis-scalp.git "$HOME/jarvis-scalp"
else
  cd "$HOME/jarvis-scalp" && git pull
fi
cd "$HOME/jarvis-scalp"

# ---------- 5. Python venv + packages ----------
echo "[5/7] Python packages install thay chhe (aa 5-10 min lai shake)..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# GPU torch (jo requirements ma na hoy / CPU version hoy to):
pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu121 || true

# ---------- 6. .env file (credentials YAHAN, code ma NAAHI) ----------
echo "[6/7] .env file check..."
if [ ! -f .env ]; then
  cat > .env <<'EOF'
# ===== SAFETY: Paper mode defaults (AA BADLAHSHO NAHI live karva vagar) =====
JARVIS_START_PAPER=1
JARVIS_PAPER=true
JARVIS_AUTO_TRADE=false

# ===== Exchange credentials (navi ROTATED keys nakho - juni revoke karo!) =====
DELTA_API_KEY=
DELTA_API_SECRET=
UPSTOX_API_KEY=
UPSTOX_API_SECRET=

# ===== Telegram alerts (optional) =====
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ===== Optional toggles (default sahi chhe) =====
# JARVIS_ENABLE_GEMINI=0      # cloud AI OFF by default
# JARVIS_WATCHDOG=1           # crash recovery ON
# JARVIS_LEARNING=1           # learning loop ON
# JARVIS_PRESIM=1             # pre-trade simulator ON
# JARVIS_KILL_SWITCH=1        # STOP_JARVIS file kill-switch ON
# JARVIS_DAILY_REPORT=1       # Telegram daily report ON
EOF
  echo "  -> .env banavyu. HUN API KEYS NAAKHJO: nano .env"
fi

# ---------- 7. GPU + Ollama model ----------
echo "[7/7] GPU check ane AI model..."
python3 -c "import torch; print('  GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NOT DETECTED - drivers check karo!')" || true
echo "  Ollama model pull thay chhe (auto-detect use karse, pan ek model joiye)..."
ollama pull phi3.5:3.8b || ollama pull qwen2.5:3b || true

echo ""
echo "=============================================="
echo "  SETUP PURU! Have aa steps follow karo:"
echo "=============================================="
echo "  1) API keys nakho:        nano ~/jarvis-scalp/.env"
echo "  2) tmux session kholo:    tmux new -s jarvis"
echo "  3) System start karo:"
echo "       cd ~/jarvis-scalp && source venv/bin/activate"
echo "       set -a && source .env && set +a"
echo "       python jarvis_FIXED.py"
echo "  4) tmux mathi bahar (system chalu rahe): Ctrl+B pachhi D"
echo "  5) Pachha connect:        tmux attach -t jarvis"
echo "  6) Emergency stop:        touch ~/jarvis-scalp/STOP_JARVIS"
echo "=============================================="
