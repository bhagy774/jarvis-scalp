"""Part 8 owned model: buffered market-structure break event head."""
from .common import candle_math, clip
FEATURE_NAMES=("break_high20","break_low20","break_high50","break_low50","swing_high_gap","swing_low_gap","range_pos20","range_pos50","slope16","ret4","atr14_pct","volume_z")
MODEL_SPEC={"task":"structure_break_event","dims":(12,22,7,3),"acts":("tanh","relu","linear"),"labels":("bear_break","no_break","bull_break"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); vals=(s["break_hi20"],s["break_lo20"],s["break_hi50"],s["break_lo50"],s["highgap"](50),s["lowgap"](50),s["range_pos20"],s["range_pos50"],s["slope16"],s["ret4"],s["atr_pct"],s["volz"])
 return tuple(clip(x) for x in vals)
def label_target(rows,i,horizon,neutral_bps,x):
 prior=rows[max(0,i-19):i+1]; hi=max(r["high"] for r in prior); lo=min(r["low"] for r in prior); atr=sum(max(r["high"]-r["low"],1e-12) for r in prior[-14:])/min(14,len(prior)); fut=rows[i+1:i+horizon+1]
 up=any(r["high"]>=hi+.15*atr for r in fut); down=any(r["low"]<=lo-.15*atr for r in fut)
 return 1 if up and down else 2 if up else 0 if down else 1
