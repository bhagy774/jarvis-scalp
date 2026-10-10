"""OFFLINE: build per-brain (features, label) datasets from historical Binance spot klines (15m).
Source: data-api.binance.vision (public market data). No orders, no keys.
Label (same for all brains, honest proxy): y=1 if a trade in TrendBrain's direction at bar close
would have been net-profitable after cost over the next HORIZON bars (default 4 x 15m = 1h).
Direction-less rows (trend_direction==0) are skipped. Rows are written in TIME ORDER per symbol,
then merged by time. Features come from each brain's own output (brain_xgb.extract_features)."""
import json, os, sys, time, urllib.request, argparse
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def fetch(symbol, interval, n_bars, cache):
    if os.path.exists(cache):
        return json.load(open(cache))
    out, end = [], None
    while len(out) < n_bars:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000" + (f"&endTime={end}" if end else "")
        with urllib.request.urlopen(url, timeout=30) as r:
            batch = json.load(r)
        if not batch: break
        out = batch + out
        end = batch[0][0] - 1
        time.sleep(0.15)
    out = out[-n_bars:]
    json.dump(out, open(cache, "w"))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--interval", default="15m")
    ap.add_argument("--bars", type=int, default=35000)
    ap.add_argument("--window", type=int, default=100)
    ap.add_argument("--step", type=int, default=4)       # non-overlapping with horizon
    ap.add_argument("--horizon", type=int, default=4)
    ap.add_argument("--cost", type=float, default=0.0010) # round-trip fee+slippage assumption
    ap.add_argument("--out", default="data/brain_xgb")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    os.environ["JARVIS_BRAIN_MODELS_DIR"] = os.path.join(a.out, "_unused")
    import brain_xgb, part1_FIXED as P
    per_brain = {}
    for sym in a.symbols.split(","):
        kl = fetch(sym, a.interval, a.bars, os.path.join(a.out, f"{sym}_{a.interval}.json"))
        pa = [{'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])} for k in kl]
        ts = [k[0] for k in kl]
        ai = P.SmartBreakoutAI()   # fresh state per symbol (no cross-symbol contamination)
        n_ok = 0
        for i in range(a.window, len(pa) - a.horizon, a.step):
            w = pa[i - a.window:i]          # candles up to and including bar i-1 (no future)
            md = {'price_action': w, 'volume_pattern': [c['volume'] for c in w]}
            res = ai.analyze(md)
            bs = res.get('brain_support') if isinstance(res, dict) else None
            if not bs: continue
            d = bs.get('trend', {}).get('trend_direction', 0)
            if d not in (1, -1): continue
            entry = pa[i - 1]['close']; exit_ = pa[i - 1 + a.horizon]['close']
            y = int(d * (exit_ - entry) / entry > a.cost)
            names = {'trend': 'trend_brain', 'volatility': 'volatility_brain', 'strength': 'strength_brain', 'risk': 'risk_brain',
                     'reversal': 'reversal_brain', 'regime': 'regime_brain', 'deepseek': 'deepseek_brain', 'evolution': 'evolution_brain',
                     'memory': 'memory_brain', 'self_heal': 'selfhealing_brain', 'meta_fusion': 'metafusion_brain',
                     'mini_r1': 'mini_r1_brain', 'mini_v3': 'mini_v3_brain'}
            for key, bname in names.items():
                f = brain_xgb.extract_features(bs.get(key, {}))
                if f: per_brain.setdefault(bname, []).append({'t': ts[i - 1], 'sym': sym, 'f': f, 'y': y})
            n_ok += 1
        print(sym, "rows used:", n_ok, flush=True)
    for b, rows in per_brain.items():
        rows.sort(key=lambda r: r['t'])
        with open(os.path.join(a.out, f"{b}.jsonl"), "w") as fh:
            for r in rows: fh.write(json.dumps(r) + "\n")
        print(b, len(rows), "base_rate=%.3f" % np.mean([r['y'] for r in rows]))

if __name__ == "__main__":
    main()
