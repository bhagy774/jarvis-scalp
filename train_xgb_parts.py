"""Offline trainer: per-symbol XGBoost on recorded Parts 1-12 outputs + 15m candle features.

Usage: python train_xgb_parts.py --symbol BTCUSDT [--horizon 4] [--cost-bps 8]

Labels come ONLY from later recorded closes of the same symbol (real outcomes):
y = 1 if close[t+horizon]/close[t]-1 > cost  (long-side win);
the model predicts P(up beyond cost); a short wins when P is low.
Chronological split with purge; the last block is untouched test data.
`validated` is written true only if out-of-sample AUC >= 0.55 on >= 300 rows.
Until enough snapshots exist this exits with 'insufficient data' (no model).
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
import numpy as np

MIN_ROWS = 1500
MIN_TEST = 300
MIN_AUC = 0.55


def load_rows(path, symbol):
    rows = []
    with open(path) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("symbol") == symbol:
                rows.append(r)
    rows.sort(key=lambda r: r["bar_ts"])
    seen, out = set(), []
    for r in rows:
        if r["bar_ts"] not in seen:
            seen.add(r["bar_ts"]); out.append(r)
    return out


def build(rows, horizon, cost):
    names = sorted({k for r in rows for k in list(r["candle"]) + list(r["parts"])})
    X = np.full((len(rows), len(names)), np.nan)
    ix = {n: i for i, n in enumerate(names)}
    for j, r in enumerate(rows):
        for d in (r["candle"], r["parts"]):
            for k, v in d.items():
                X[j, ix[k]] = v
    close = np.array([r["close"] for r in rows])
    bars = np.array([r["bar_ts"] for r in rows])
    y = np.full(len(rows), np.nan)
    for j in range(len(rows) - horizon):
        # only a contiguous 15m sequence counts as a real forward outcome
        if abs((bars[j + horizon] - bars[j]) - horizon * 900) <= 60:
            y[j] = 1.0 if close[j + horizon] / close[j] - 1.0 > cost else 0.0
    return names, X, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--log", default="logs/part_snapshots.jsonl")
    ap.add_argument("--out", default="models")
    ap.add_argument("--horizon", type=int, default=4)
    ap.add_argument("--cost-bps", type=float, default=8.0)
    a = ap.parse_args()
    sym = a.symbol.upper()
    rows = load_rows(a.log, sym)
    if len(rows) < MIN_ROWS:
        print(f"insufficient data: {len(rows)} snapshots for {sym} (need >= {MIN_ROWS}); no model written")
        return 2
    names, X, y = build(rows, a.horizon, a.cost_bps / 1e4)
    ok = np.isfinite(y)
    X, y = X[ok], y[ok]
    n = len(y)
    i_tr, i_va = int(n * 0.6), int(n * 0.8)
    purge = a.horizon
    import xgboost as xgb
    from sklearn.metrics import roc_auc_score
    Xtr, ytr = X[:i_tr], y[:i_tr]
    Xva, yva = X[i_tr + purge:i_va], y[i_tr + purge:i_va]
    Xte, yte = X[i_va + purge:], y[i_va + purge:]
    if len(yte) < MIN_TEST or len(set(yte)) < 2 or len(set(yva)) < 2:
        print("insufficient labelled out-of-sample rows; no model written"); return 2
    prm = dict(objective="binary:logistic", eval_metric="auc", max_depth=3, eta=0.05,
               subsample=0.8, colsample_bytree=0.7, min_child_weight=20, tree_method="hist")
    dtr = xgb.DMatrix(Xtr, label=ytr, feature_names=names)
    dva = xgb.DMatrix(Xva, label=yva, feature_names=names)
    bst = xgb.train(prm, dtr, 400, evals=[(dva, "val")], early_stopping_rounds=30, verbose_eval=False)
    pte = bst.predict(xgb.DMatrix(Xte, feature_names=names))
    auc = float(roc_auc_score(yte, pte))
    base_rate = float(yte.mean())
    validated = bool(auc >= MIN_AUC and len(yte) >= MIN_TEST)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    bst.save_model(str(out / f"xgb_parts_{sym}_15m.json"))
    meta = dict(symbol=sym, timeframe="15m", version=int(time.time()), feature_names=names,
                horizon_bars=a.horizon, cost_bps=a.cost_bps, data_kind="recorded_live_snapshots",
                n_rows=int(n), threshold=0.45, base_rate_test=base_rate,
                oos=dict(auc=auc, n_test=int(len(yte))), validated=validated)
    (out / f"xgb_parts_{sym}_15m.meta.json").write_text(json.dumps(meta, indent=2))
    print(f"{sym}: rows={n} test_auc={auc:.3f} base_rate={base_rate:.3f} validated={validated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
