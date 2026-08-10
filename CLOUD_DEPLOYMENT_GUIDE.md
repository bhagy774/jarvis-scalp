# 🚀 Jarvis Trade Elite - Cloud Deployment Guide

આ ફાઈલ તમને **Jarvis Trade Elite** ને ક્લાઉડ સર્વર (Cloud Server) પર 24/7 રન કરવા માટેની સંપૂર્ણ માહિતી આપશે. આ સિસ્ટમમાં AI (Ollama) અને PyTorch (GPU) નો ઉપયોગ થતો હોવાથી સામાન્ય સર્વરના બદલે **GPU Cloud Server** લેવો જરૂરી છે.

---

## 1️⃣ સર્વર સિલેક્શન (Server Selection)
તમારે એક એવું સર્વર લેવું પડશે જેમાં **NVIDIA GPU** હોય. 
- **સૌથી સસ્તો અને બેસ્ટ ઓપ્શન:** [RunPod.io](https://www.runpod.io/) અથવા Vast.ai 
- **OS (ઓપરેટિંગ સિસ્ટમ):** Ubuntu 22.04 LTS (Linux)
- **Minimum Requirement:** 
  - GPU: RTX 3060 / 4060 / A4000 (minimum 8GB VRAM)
  - RAM: 16 GB
  - Storage: 50 GB SSD

---

## 2️⃣ સર્વર સેટઅપ (Initial Setup)
તમારું સર્વર ચાલુ થાય એટલે Terminal / SSH દ્વારા લોગીન કરો અને નીચેના કમાન્ડ વારાફરતી રન કરો:

### Step 1: System Update
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git screen -y
```

### Step 2: GitHub માંથી કોડ ડાઉનલોડ કરવો
```bash
git clone https://github.com/bhagy774/jarvis-scalp.git
cd jarvis-scalp
```

### Step 3: Python Virtual Environment બનાવવું
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Python Libraries Install કરવી
આપણા સિસ્ટમને PyTorch અને CUDA ની જરૂર છે.
```bash
# PyTorch with CUDA support (for Linux)
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install other requirements
pip install -r requirements.txt
pip install websockets pandas numpy requests
```

---

## 3️⃣ Ollama સેટઅપ (Local AI Models માટે)
આપણી સિસ્ટમમાં Part 9, Part 11 અને Self-Diagnosis માટે Ollama ની જરૂર છે.

### Step 1: Ollama ઇન્સ્ટોલ કરો
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: જરૂરી AI Models ડાઉનલોડ કરો
```bash
ollama pull tinyllama     # For fast health diagnostic
ollama pull qwen2.5:0.5b  # For fast trading decisions
ollama pull llama3        # For Deep reasoning (optional)
```

---

## 4️⃣ Environment Setup (.env ફાઈલ)
તમારે તમારા API Keys નાખવા પડશે. 
```bash
nano .env
```
અંદર આટલી વિગતો નાખો (તમારી અસલી Keys સાથે):
```env
# Delta Exchange API (For Real/Paper Trading)
DELTA_API_KEY=your_delta_api_key_here
DELTA_API_SECRET=your_delta_api_secret_here

# OpenRouter (For DeepSeek V3 / R1)
OPENROUTER_API_KEY=your_openrouter_key_here

# Mode
TRADING_MODE=PAPER_TRADING  # (જો લાઈવ પૈસાથી કરવું હોય તો LIVE_TRADING લખવું)
```
*(Save કરવા માટે `Ctrl + X` દબાવો, પછી `Y` અને `Enter`)*

---

## 5️⃣ 24/7 બેકગ્રાઉન્ડમાં રન કરવું (Live Run)
તમારું કમ્પ્યુટર બંધ થાય તો પણ સર્વર પર Jarvis ચાલતો રહેવો જોઈએ. એના માટે આપણે `screen` કમાન્ડ નો ઉપયોગ કરીશું.

### Step 1: નવી Screen બનાવો
```bash
screen -S jarvis_live
```

### Step 2: સિસ્ટમ રન કરો
```bash
# Virtual environment એક્ટિવ ના હોય તો કરો
source venv/bin/activate

# સિસ્ટમ સ્ટાર્ટ કરો
python run_all_parts.py
```

### Step 3: બેકગ્રાઉન્ડમાં છોડી દો (Detach)
હવે તમારા કીબોર્ડ પર દબાવો:
`Ctrl + A` અને પછી `D`
(આનાથી સિસ્ટમ બેકગ્રાઉન્ડમાં ચાલતી રહેશે અને તમે ટર્મિનલ બંધ કરી શકો છો).

### (ફરીથી જોવા માટે)
જ્યારે તમારે પાછું જોવું હોય કે ટ્રેડિંગ કેવું ચાલે છે, ત્યારે આ કમાન્ડ લખો:
```bash
screen -r jarvis_live
```

---

## 📝 ચેક કરવા માટેના લોગ્સ (Monitoring)
તમે ક્લાઉડમાં બે ફાઈલો ચેક કરી શકો છો:
1. **AI ના વિચારો:** `cat logs/jarvis_thoughts.log`
2. **પેપર ટ્રેડિંગ રિપોર્ટ:** `cat logs/trade_history.json`

**Best of Luck! તમારું Wall Street લેવલનું HFT Engine હવે ક્લાઉડ પર ઉડવા માટે તૈયાર છે!** 🚀
