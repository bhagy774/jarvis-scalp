"""Part 1 owned model: ATR-normalized first-touch breakout classifier."""
from .common import candle_math, clip
FEATURE_NAMES=("ret1","ret4","ret16","break_high20","break_low20","range_pos20","volume_z","body_signed","slope16","atr14_pct","vol_ratio","wick_imbalance")
MODEL_SPEC={"task":"first_touch_breakout","dims":(12,20,8,3),"acts":("relu","tanh","linear"),"labels":("bear_break","no_break","bull_break"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); r=s["rows"][-1]; ran=s["range"][-1]
 vals=(s["ret1"],s["ret4"],s["ret16"],s["break_hi20"],s["break_lo20"],s["range_pos20"],s["volz"],(r["close"]-r["open"])/ran,s["slope16"],s["atr_pct"],s["vol_ratio"],s["wick_imbalance"])
 return tuple(clip(x) for x in vals)
def label_target(rows,i,horizon,neutral_bps,x):
 future=rows[i+1:i+horizon+1]; recent=rows[max(0,i-13):i+1]
 atr=sum(max(r["high"]-r["low"],1e-12) for r in recent)/len(recent); up=rows[i]["close"]+.6*atr; down=rows[i]["close"]-.6*atr
 for r in future:
  hit_up=r["high"]>=up; hit_down=r["low"]<=down
  if hit_up and hit_down:return 1
  if hit_up:return 2
  if hit_down:return 0
 return 1
