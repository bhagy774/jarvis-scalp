"""Part 2 model: clustered structural zones and range-overlap auction evidence."""
from .common import candle_math, clip
FEATURE_NAMES=("support_distance_risk_scale","resistance_distance_risk_scale","support_cluster_strength","resistance_cluster_strength","poc_distance_risk_scale","close_location_in_value_area","range_position32","robust_trend_score","state_velocity_z","volume_surprise_robust_z","ohlcv_flow_imbalance_proxy","range_width50_pct")
MODEL_SPEC={"task":"volume_zone_response","dims":(12,16,6,3),"acts":("tanh","relu","linear"),"labels":("support_rejection","zone_acceptance","resistance_rejection"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); p=s["profile"]
 vals=(s["support_distance_scale"],s["resistance_distance_scale"],s["support_strength"],s["resistance_strength"],s["poc_distance_scale"],s["close_location_in_value"],s["range_position_32"],s["trend_score"],s["state_velocity_z"],s["volume_surprise_z"],s["flow_proxy"],s["range_width_50_pct"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"zone_response":prediction,"support_rejection_score_uncalibrated":scores[0],"resistance_rejection_score_uncalibrated":scores[2]}
def label_target(rows,i,horizon,neutral_bps,x):
 prior=rows[max(0,i-31):i+1]; lo=min(r["low"] for r in prior); hi=max(r["high"] for r in prior); pos=(rows[i]["close"]-lo)/max(hi-lo,1e-12); ret=rows[i+horizon]["close"]/rows[i]["close"]-1; t=neutral_bps/10000
 if pos<=.35 and ret>t:return 0
 if pos>=.65 and ret< -t:return 2
 return 1
