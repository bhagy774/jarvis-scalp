"""Part 10 owned model: candle-state transitions and streak statistics."""
from .common import candle_math, clip
FEATURE_NAMES=("body_ratio","body_acceleration","streak8","transition_rate16","green_fraction16","range_atr","ret1","ret4","ret16","drawdown16","volume_z","vol_ratio")
MODEL_SPEC={"task":"candle_transition","dims":(12,12,6,3),"acts":("relu","tanh","linear"),"labels":("reversal","indecision","continuation"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); vals=(s["body_ratio"],s["body"][-1]-s["body"][-2],s["streak"],s["transition"],s["green_fraction"],s["range_atr"],s["ret1"],s["ret4"],s["ret16"],s["drawdown16"],s["volz"],s["vol_ratio"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"candle_transition":prediction,"reversal_score_uncalibrated":scores[0],"continuation_score_uncalibrated":scores[2]}
def label_target(rows,i,horizon,neutral_bps,x):
 body=rows[i]["close"]-rows[i]["open"]; ret=rows[i+horizon]["close"]/rows[i]["close"]-1
 if not body or abs(ret)<neutral_bps/10000:return 1
 return 0 if ret*body<0 else 2
