"""OFFLINE: train each Part 1 brain's micro-XGBoost from data/brain_xgb/<brain>.jsonl (time-ordered).
Compares against baselines on a held-out LATER period (time split; no shuffle):
  base_rate  = fraction of profitable trend-direction trades (always-trade)
  precision@top20% = win rate when model confidence is in its top 20% (selective trading)
Saves a model only if val AUC >= min_val_auc. Writes report JSON/MD. No live effect (shadow only)."""
import json, os, sys, argparse
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data/brain_xgb"); ap.add_argument("--models", default="models")
ap.add_argument("--min_auc", type=float, default=0.55)
a = ap.parse_args()
os.environ["JARVIS_BRAIN_MODELS_DIR"] = a.models
import brain_xgb, xgboost as xgb
brain_xgb.MODELS_DIR = a.models
report = {}
for fn in sorted(os.listdir(a.data)):
    if not fn.endswith(".jsonl"): continue
    name = fn[:-6]
    rows = [json.loads(l) for l in open(os.path.join(a.data, fn))]
    rep = brain_xgb.train_brain_model(name, rows, min_val_auc=a.min_auc)
    # extra: precision of top-20% confidence on the held-out tail
    if rep.get("val_auc") is not None:
        names = sorted(rows[0]["f"]); rows2 = [r for r in rows if sorted(r["f"]) == names]
        cut = int(len(rows2) * .75); tr, va = rows2[:cut], rows2[cut:]
        X = lambda rs: np.array([[r["f"][k] for k in names] for r in rs], dtype=np.float32)
        y = np.array([r["y"] for r in va])
        b = xgb.train({"objective": "binary:logistic", "max_depth": 3, "eta": .1, "subsample": .8, "tree_method": "hist", "seed": 7},
                      xgb.DMatrix(X(tr), label=[r["y"] for r in tr], feature_names=names), 100)
        p = b.predict(xgb.DMatrix(X(va), feature_names=names))
        k = max(1, int(len(p) * .2)); top = np.argsort(-p)[:k]
        rep["precision_top20"] = float(y[top].mean()); rep["val_n"] = len(va)
    report[name] = rep
    print(name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in rep.items()}, flush=True)
json.dump(report, open(os.path.join(a.data, "train_report.json"), "w"), indent=1)
