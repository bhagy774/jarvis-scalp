"""Part 6 owned model: directional movement / trend persistence head."""
from .common import candle_math, clip
FEATURE_NAMES=("ema8_21","ema21_50","slope16","slope32","up_move14","down_move14","directional_imbalance","ret4","ret16","range_pos32","vol_ratio","atr14_pct")
MODEL_SPEC={"task":"trend_persistence","dims":(12,12,4,1),"acts":("tanh","relu","linear"),"labels":("trend_break","trend_persists"),"kind":"sigmoid"}
def prepare_features(data):
 s=candle_math(data); vals=(s["ema821"],s["ema2150"],s["slope16"],s["slope32"],s["up_move14"],s["down_move14"],s["directional_imbalance"],s["ret4"],s["ret16"],s["range_pos32"],s["vol_ratio"],s["atr_pct"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"trend_persistence":prediction,"trend_persistence_score_uncalibrated":scores[1]}
def label_target(rows,i,horizon,neutral_bps,x):
 directional=x[0]+x[1]+x[2]
 if abs(directional)<1e-7:return 0
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1
 return int(abs(ret)>=neutral_bps/10000 and ret*directional>0)
