"""Part 2 owned model: volume-node and zone-rejection head."""
from .common import candle_math, clip
FEATURE_NAMES=("range_pos32","dist_weighted_mean","dist_high32","dist_low32","volume_node_pos","volume_z","ret4","ret16","atr14_pct","range_pos8","trend_slope","range_expansion")
MODEL_SPEC={"task":"volume_zone_response","dims":(12,16,6,3),"acts":("tanh","relu","linear"),"labels":("support_rejection","zone_acceptance","resistance_rejection"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); vals=(s["range_pos32"],s["weighted_dev"],s["highgap"](32),s["lowgap"](32),s["volume_node_pos"],s["volz"],s["ret4"],s["ret16"],s["atr_pct"],s["pos"](8),s["slope32"],s["range_expansion"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"zone_response":prediction,"support_rejection_score_uncalibrated":scores[0],"resistance_rejection_score_uncalibrated":scores[2]}
def label_target(rows,i,horizon,neutral_bps,x):
 prior=rows[max(0,i-31):i+1]; lo=min(r["low"] for r in prior); hi=max(r["high"] for r in prior); pos=(rows[i]["close"]-lo)/max(hi-lo,1e-12); ret=rows[i+horizon]["close"]/rows[i]["close"]-1; t=neutral_bps/10000
 if pos<=.35 and ret>t:return 0
 if pos>=.65 and ret< -t:return 2
 return 1
