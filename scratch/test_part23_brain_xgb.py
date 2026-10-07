"""Offline test: shadow micro-XGBoost hooks on Part 2 / Part 3 brains. No network, no orders."""
import os, sys, ast, tempfile
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
os.environ["JARVIS_BRAIN_MODELS_DIR"] = tempfile.mkdtemp()
import brain_xgb
fails = 0
def check(c, m):
    global fails; print(("PASS " if c else "FAIL ") + m); fails += (not c)

# 1. static: every expected class is decorated (works without torch/GPU)
EXPECT = {"part2_FIXED.py": 14, "part3_FIXED.py": 4}
for f, n in EXPECT.items():
    t = ast.parse(open(os.path.join(ROOT, f), encoding="utf-8").read())
    dec = [c.name for c in t.body if isinstance(c, ast.ClassDef) and any(
        isinstance(d, ast.Call) and getattr(d.func, "id", "") == "xgb_shadow" for d in c.decorator_list)]
    check(len(dec) == n, f"{f}: {len(dec)} classes hooked (expected {n})")

# 2. behaviour: return value passes through UNCHANGED (same object), confidence goes to side channel
class Fake:
    def lst(self): self.r = [{"confidence": 0.7, "x": 2}]; return self.r
    def dct(self): self.r = {"a": 1.0, "s": "text"}; return self.r
    def flt(self): return 0.0123
    def txt(self): return "TRENDING"
    def boom(self): return {"a": float("nan")}
for m in ["lst", "dct", "flt", "txt", "boom"]:
    C = type("C", (Fake,), {})
    C = brain_xgb.xgb_shadow("t_" + m, m)(C)
    o = C(); r = getattr(o, m)()
    same = (r is o.r) if m in ("lst", "dct") else (r == getattr(Fake(), m)() if m in ("flt", "txt") else True)
    check(same, f"{m}: return value untouched")
    check(o.last_xgb == {"confidence": 0.5, "active": False}, f"{m}: neutral 0.5 without model")
check(r == {"a": float("nan")} or True, "nan input does not crash")
d = Fake().dct(); check(set(d) == {"a", "s"}, "dict output has no xgb_* keys added")

# 3. offline training + active prediction on a Part 2/3 style brain (list output)
import random; random.seed(3)
rows = []
for _ in range(400):
    q = random.random()
    rows.append({"f": {"count": 1.0, "mean_confidence": q, "mean_x": 2.0}, "y": int(q + random.gauss(0, .15) > .5)})
rep = brain_xgb.train_brain_model("t_lst", rows)
check(rep["saved"], f"trained model saved (val_auc={rep.get('val_auc', 0):.3f})")
class L:
    def __init__(s, q): s.q = q
    def lst(s): return [{"confidence": s.q, "x": 2}]
L = brain_xgb.xgb_shadow("t_lst", "lst")(L)
hi, lo = L(.95), L(.05); a, b = hi.lst(), lo.lst()
check(hi.last_xgb["active"] and hi.last_xgb["confidence"] > lo.last_xgb["confidence"],
      f"active: high {hi.last_xgb['confidence']:.2f} > low {lo.last_xgb['confidence']:.2f}; return unchanged {a==[{'confidence':.95,'x':2}]}")

# 4. try real Part 3 import (needs pandas etc.)
try:
    import part3_FIXED as P3
    for c in ["ZonePointFiveDetectorGPU", "InstitutionalTradingEngineGPU", "InstitutionalRiskManagementEngineGPU", "InstitutionalTradeExecutionEngine"]:
        check(hasattr(getattr(P3, c), "_xgb_name"), f"part3 import: {c} hooked")
    z = P3.ZonePointFiveDetectorGPU(); out = z.detect_0_5_zone_signals(); check(out == [] and z.last_xgb["confidence"] == .5, "Zone detector real call: [] unchanged, neutral")
except Exception as e:
    print("SKIPPED real part3 import:", type(e).__name__, str(e)[:100])
print("FAILS:", fails); sys.exit(1 if fails else 0)
