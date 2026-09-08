#!/usr/bin/env python3
"""
JARVIS HUD Server — WebSocket Bridge
CognitiveBus THOUGHTS/HEALTH → WebSocket → Browser Dashboard
Serves the 3D dashboard at http://localhost:7788
"""

import asyncio
import json
import logging
import os
import random
import time
import threading
from datetime import datetime
from typing import Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s [HUD] %(message)s")
logger = logging.getLogger("JarvisHUD")

app = FastAPI(title="JARVIS HUD Server")

# ── Connected WebSocket clients ─────────────────────────────
connected_clients: Set[WebSocket] = set()

# ── Live State (shared between bus thread and WS broadcaster) ─
state = {
    "parts": {},          # Part1_Breakout: {direction, confidence, raw, ts}
    "trades": [],         # list of trade dicts
    "stats": {
        "wins": 0, "losses": 0, "total_pnl": 0.0,
        "equity_curve": [], "win_rate": 0.0
    },
    "health": {},         # partName: {severity, ts}
    "pipeline": {
        "watcher_active": False,
        "last_packet_ts": None,
        "specialist_opinions": {}
    },
    "oracle": {},         # JARVIS Market Oracle multi-timeframe forecast
    "chat_history": [],
    "system_online": True,
}

# ── Broadcast to all connected clients ──────────────────────
async def broadcast(payload: dict):
    global connected_clients
    dead = set()
    msg  = json.dumps(payload)
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    connected_clients -= dead


# ── CognitiveBus integration ────────────────────────────────
def start_bus_listener():
    """Runs in a background thread. Hooks into the real CognitiveBus if available."""
    # Pre-load initial market map from disk if present
    try:
        map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "jarvis_market_map.json")
        if os.path.exists(map_path):
            with open(map_path, "r", encoding="utf-8") as f:
                state["oracle"] = json.load(f)
                logger.info("Loaded initial Oracle Market Map from disk")
    except Exception as me:
        logger.debug(f"Could not load initial market map: {me}")

    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from jarvis_cognitive_bus import CognitiveBus
        from jarvis_watcher_ai import JarvisWatcherAI

        bus     = CognitiveBus()
        watcher = JarvisWatcherAI(bus=bus)
        watcher.start()
        state["pipeline"]["watcher_active"] = True
        logger.info("CognitiveBus connected — live data mode ACTIVE")

        def on_thoughts(msg):
            sender  = msg.get("sender", "Unknown")
            payload = msg.get("payload", "")
            # Update part state
            state["parts"][sender] = {
                "direction":  _extract_direction(payload),
                "confidence": _extract_confidence(payload),
                "raw":        str(payload)[:100],
                "ts":         datetime.now().isoformat()
            }
            state["pipeline"]["last_packet_ts"] = datetime.now().isoformat()

        def on_health(msg):
            sender   = msg.get("sender", "Unknown")
            payload  = msg.get("payload", {})
            severity = payload.get("severity", "WARNING") if isinstance(payload, dict) else "WARNING"
            state["health"][sender] = {"severity": severity, "ts": datetime.now().isoformat()}

        def on_oracle(msg):
            payload = msg.get("payload", {})
            if isinstance(payload, dict):
                state["oracle"] = payload
                logger.info("HUD received live ORACLE_FORECAST update")

        bus.subscribe("THOUGHTS", on_thoughts)
        bus.subscribe("HEALTH",   on_health)
        bus.subscribe("ORACLE_FORECAST", on_oracle)

    except Exception as e:
        logger.warning(f"CognitiveBus not available — using DEMO mode: {e}")
        _start_demo_data()

# ── Terminal Log Tailer ──────────────────────────────────────
def start_terminal_tailer():
    """Tails jarvis_terminal.log and pushes new lines to state."""
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "jarvis_terminal.log")
    if not os.path.exists(log_file):
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, 'w') as f: f.write("")
        except:
            pass

    state["terminal_logs"] = []
    
    def _tail():
        while not os.path.exists(log_file):
            time.sleep(1)
        
        with open(log_file, 'r', encoding='utf-8') as f:
            # Go to the end of the file initially to avoid sending old logs
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                
                # Add to state and limit size
                state["terminal_logs"].append(line)
                if len(state["terminal_logs"]) > 200:
                    state["terminal_logs"] = state["terminal_logs"][-200:]
                    
                # Parsing logic for specific advanced engines
                if "⚛️ QUANTUM" in line:
                    state["pipeline"]["quantum_status"] = line.strip()
                elif "🛡️ HEDGE ADVISOR" in line or "🚀 Executed Dual-Leg" in line:
                    state["pipeline"]["hedge_status"] = line.strip()
                elif "[PART 1 OLLAMA LIVE THOUGHTS]" in line or "🧠 AI RATIONALE:" in line:
                    # Very simple capture - wait for actual lines in frontend
                    state["pipeline"]["ai_rationale_trigger"] = datetime.now().isoformat()

    threading.Thread(target=_tail, daemon=True).start()
    logger.info("Terminal tailer started")


def _extract_direction(text: str) -> str:
    t = str(text).upper()
    if "BULLISH" in t or "CALL" in t or "BUY" in t:
        return "BULLISH"
    if "BEARISH" in t or "PUT" in t or "SELL" in t:
        return "BEARISH"
    return "NEUTRAL"


def _extract_confidence(text: str) -> float:
    import re
    m = re.search(r"(?:confidence|score|avg score)[^\d]*([0-9]+\.?[0-9]*)", str(text), re.IGNORECASE)
    if m:
        v = float(m.group(1))
        return v * 100.0 if v <= 1.5 else v
    return round(random.uniform(50, 90), 1)


# ── Demo / Simulation Mode ───────────────────────────────────
PART_NAMES = [
    "Part1_Breakout", "Part2_Neural", "Part3_Institutional",
    "Part4_Backtest", "Part5_Fusion", "Part6_Backtest",
    "Part7_LiveData", "Part8_Pattern", "Part9_Adaptive",
    "Part10_Execution", "Part11_Confidence", "Part12_Execution"
]

DEMO_THOUGHTS = {
    "Part1_Breakout":      "Breakout Analysis: BULLISH (Signal: 1, Confidence: 7.42). Regime: trending",
    "Part2_Neural":        "Neural Network Predictions: BULLISH (Avg score: 0.76)",
    "Part3_Institutional": "Institutional MTF Analysis: BULLISH (Consensus: 0.62). Dominant Regime: trending",
    "Part4_Backtest":      "Backtest Engine: Completed in 3.2s. Data points: 5000",
    "Part5_Fusion":        "Fusion Engine (MTF): Consensus = 0.48, Direction = CALL, Confidence = 81.5%",
    "Part6_Backtest":      "Backtest Complete: Trades=142, WinRate=0.76, PnL=8420.0. Duration=12.4s",
    "Part7_LiveData":      "Live Data Engine: Price=67420.5, Volume=18342.22, Symbol=BTCUSDT",
    "Part8_Pattern":       "Pattern Recognition: Bullish Engulfing detected. BULLISH. Confidence = 77.0%",
    "Part9_Adaptive":      "Adaptive Learning: Status=RUNNING. Strategy Recommendation: Increase trend weight",
    "Part10_Execution":    "Execution Engine: Direction=BUY, Confidence=82%. Entry price=67420.0",
    "Part11_Confidence":   "Confidence Engine: Final Score = 88.0%. VALID | Ollama Adj: +5",
    "Part12_Execution":    "Execution Analytics: Position=LONG, PnL=342.50, Return=1.24%, Total Trades=59",
}

_equity_base = 10000.0

def _start_demo_data():
    """Simulate live data when no real CognitiveBus is present."""
    global _equity_base
    state["pipeline"]["watcher_active"] = True

    # Init all parts
    for name, thought in DEMO_THOUGHTS.items():
        state["parts"][name] = {
            "direction":  _extract_direction(thought),
            "confidence": _extract_confidence(thought),
            "raw":        thought[:100],
            "ts":         datetime.now().isoformat()
        }

    # Init equity curve
    val = 10000.0
    curve = []
    for i in range(60):
        val += random.gauss(25, 80)
        curve.append(round(val, 2))
    state["stats"]["equity_curve"] = curve
    state["stats"]["wins"]         = 47
    state["stats"]["losses"]       = 12
    state["stats"]["total_pnl"]    = round(val - 10000.0, 2)
    state["stats"]["win_rate"]     = round(47 / 59 * 100, 1)

    # Initial trade
    state["trades"] = [{
        "symbol":    "BTC/USDT",
        "direction": "LONG",
        "entry":     67420.0,
        "current":   67762.5,
        "pnl":       342.5,
        "risk_pct":  1.2,
        "tp":        68500.0,
        "sl":        66800.0,
        "ts":        datetime.now().isoformat()
    }]

    def _demo_tick():
        global _equity_base
        directions = ["BULLISH", "BEARISH", "NEUTRAL"]
        weights    = [0.6, 0.25, 0.15]
        part_list  = list(DEMO_THOUGHTS.keys())
        idx        = 0

        while True:
            time.sleep(2.0)
            # Rotate through parts — update 2 per tick for live feel
            for _ in range(2):
                part = part_list[idx % len(part_list)]
                idx += 1
                conf = round(random.uniform(55, 95), 1)
                direction = random.choices(directions, weights)[0]
                state["parts"][part] = {
                    "direction":  direction,
                    "confidence": conf,
                    "raw":        f"{part}: {direction} (Confidence: {conf}%)",
                    "ts":         datetime.now().isoformat()
                }

            # Update live trade P&L
            if state["trades"]:
                t   = state["trades"][0]
                t["current"] = round(t["current"] + random.gauss(0, 15), 1)
                t["pnl"]     = round((t["current"] - t["entry"]) * 0.01, 2)
                t["ts"]      = datetime.now().isoformat()

            # Equity curve rolling
            last = state["stats"]["equity_curve"][-1] if state["stats"]["equity_curve"] else 10000.0
            last += random.gauss(8, 45)
            state["stats"]["equity_curve"].append(round(last, 2))
            if len(state["stats"]["equity_curve"]) > 120:
                state["stats"]["equity_curve"] = state["stats"]["equity_curve"][-120:]

            state["pipeline"]["last_packet_ts"] = datetime.now().isoformat()

    t = threading.Thread(target=_demo_tick, daemon=True)
    t.start()
    logger.info("DEMO mode active — simulating all 12 Parts live data")


# ── State push loop ──────────────────────────────────────────
async def state_push_loop():
    """Broadcasts full state to all clients every 1 second."""
    while True:
        await asyncio.sleep(1.0)
        if connected_clients:
            await broadcast({"type": "STATE_UPDATE", "data": state})


# ── WebSocket endpoint ───────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"Client connected. Total: {len(connected_clients)}")
    # Send full state immediately
    await ws.send_text(json.dumps({"type": "STATE_UPDATE", "data": state}))
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "CHAT":
                await handle_chat(ws, msg.get("text", ""))
    except WebSocketDisconnect:
        connected_clients.discard(ws)
        logger.info(f"Client disconnected. Total: {len(connected_clients)}")


async def handle_chat(ws: WebSocket, user_text: str):
    state["chat_history"].append({"role": "user", "text": user_text, "ts": datetime.now().isoformat()})
    # Try real Ollama, fallback to canned response
    reply = await asyncio.get_event_loop().run_in_executor(None, _call_jarvis_chat, user_text)
    state["chat_history"].append({"role": "jarvis", "text": reply, "ts": datetime.now().isoformat()})
    await broadcast({"type": "CHAT_REPLY", "role": "jarvis", "text": reply})


def _call_jarvis_chat(user_text: str) -> str:
    try:
        from ollama_integration import call_ollama
        agg = state.get("parts", {})
        context = f"JARVIS Trading System. Active parts: {len(agg)}. User asks: {user_text}"
        resp, err = call_ollama(context, model="qwen2.5:14b", timeout=15)
        return resp.strip() if resp else f"Ollama unavailable: {err}"
    except Exception as e:
        return f"Chat unavailable: {e}"


# ── Serve dashboard HTML ─────────────────────────────────────
@app.get("/")
async def serve_dashboard():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_hud", "index.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/oracle")
async def get_oracle_map():
    """Return latest Market Oracle multi-timeframe forecast."""
    return state.get("oracle", {})


# ── Startup ──────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("JARVIS HUD Server starting...")
    threading.Thread(target=start_bus_listener, daemon=True).start()
    start_terminal_tailer()
    asyncio.create_task(state_push_loop())
    logger.info("HUD Server ONLINE → http://localhost:7788")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7788, log_level="warning")
