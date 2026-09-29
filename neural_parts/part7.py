"""Part 7 owned model: future realized-volatility regime head, not a gate."""
from .common import candle_math, clip, mean
FEATURE_NAMES=("std8","std32","vol_ratio","atr14_pct","atr14_50_ratio","range_atr","range_expansion","ret1","abs_ret4","abs_ret16","body_ratio","volume_z")
MODEL_SPEC={"task":"future_volatility_regime","dims":(12,16,8,3),"acts":("relu","tanh","linear"),"labels":("contracting","normal","expanding"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); vals=(s["ret8std"],s["ret32std"],s["vol_ratio"],s["atr_pct"],s["atr14"]/max(s["atr50"],1e-12),s["range_atr"],s["range_expansion"],s["ret1"],abs(s["ret4"]),abs(s["ret16"]),s["body_ratio"],s["volz"])
 return tuple(clip(x) for x in vals)
def label_target(rows,i,horizon,neutral_bps,x):
 past=[math.log(rows[j]["close"]/rows[j-1]["close"]) for j in range(max(1,i-31),i+1)]; future=[math.log(rows[j]["close"]/rows[j-1]["close"]) for j in range(i+1,i+horizon+1)]
 def sd(a):
  m=mean(a); return math.sqrt(mean([(v-m)**2 for v in a]))
 ratio=sd(future)/max(sd(past),1e-12)
 return 0 if ratio<.75 else 2 if ratio>1.25 else 1
import math
