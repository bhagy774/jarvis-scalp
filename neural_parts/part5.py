"""Part 5 owned model: normalized drift and regression-stat head."""
from .common import candle_math, clip, div, std
FEATURE_NAMES=("drift_z16","slope_t_proxy","ret1","ret4","ret16","ema8_21","ema21_50","rsi_centered","volume_z","vol_ratio","atr14_pct","drawdown16")
MODEL_SPEC={"task":"forward_return_direction","dims":(12,24,12,3),"acts":("relu","tanh","linear"),"labels":("down_return","neutral_return","up_return"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); drift=div(sum(s["returns"][-16:])/16, std(s["returns"][-16:])); tproxy=div(s["slope16"],std(s["returns"][-16:]))
 vals=(drift,tproxy,s["ret1"],s["ret4"],s["ret16"],s["ema821"],s["ema2150"],s["ema_rsi"],s["volz"],s["vol_ratio"],s["atr_pct"],s["drawdown16"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"forward_return_bucket":prediction,"down_score_uncalibrated":scores[0],"up_score_uncalibrated":scores[2]}
def label_target(rows,i,horizon,neutral_bps,x):
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1; t=neutral_bps/10000
 return 2 if ret>t else 0 if ret< -t else 1
