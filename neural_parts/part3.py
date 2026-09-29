"""Part 3 owned model: body/wick anatomy reversal detector."""
from .common import candle_math, clip, div
FEATURE_NAMES=("body_ratio","upper_wick_ratio","lower_wick_ratio","close_location","range_atr","gap_atr","prev_body_signed","engulf_proxy","doji_proxy","ret1","ret4","volume_z")
MODEL_SPEC={"task":"candle_reversal","dims":(12,10,4,1),"acts":("tanh","relu","linear"),"labels":("no_reversal","reversal"),"kind":"sigmoid"}
def prepare_features(data):
 s=candle_math(data); r=s["rows"][-1]; body=s["body"][-1]; prev=s["body"][-2]; rng=s["range"][-1]
 gap=div(r["open"]-s["prior_close"],s["atr14"]); engulf=(1.0 if body>0 else -1.0) if abs(body)>abs(prev) and body*prev<0 else 0.0
 vals=(s["body_ratio"],s["upper"][-1],s["lower"][-1],s["close_location"],s["range_atr"],gap,prev,engulf,1-s["body_ratio"],s["ret1"],s["ret4"],s["volz"])
 return tuple(clip(x) for x in vals)
def label_target(rows,i,horizon,neutral_bps,x):
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1; body=rows[i]["close"]-rows[i]["open"]
 return int(bool(body and abs(ret)>=neutral_bps/10000 and ret*body<0))
