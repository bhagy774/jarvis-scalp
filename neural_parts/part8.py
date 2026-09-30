"""Part 8 owned model: buffered structural-break evidence head."""
from .common import candle_math, clip
FEATURE_NAMES=("downside_break20_risk_scale","upside_break20_risk_scale","downside_break50_risk_scale","upside_break50_risk_scale","support_distance_risk_scale","resistance_distance_risk_scale","range_position20","range_position50","robust_trend_score","return4_robust_z","range_scale_pct","volume_surprise_robust_z")
MODEL_SPEC={"task":"structure_break_event","dims":(12,22,7,3),"acts":("tanh","relu","linear"),"labels":("bear_break","no_break","bull_break"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); vals=(s["break_low20_scale"],s["break_high20_scale"],s["break_low50_scale"],s["break_high50_scale"],s["support_distance_scale"],s["resistance_distance_scale"],s["range_position_20"],s["range_position_50"],s["trend_score"],s["ret4_z"],s["range_scale_pct"],s["volume_surprise_z"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"structure_break_event":prediction,"bear_break_score_uncalibrated":scores[0],"bull_break_score_uncalibrated":scores[2]}
def label_target(rows,i,horizon,neutral_bps,x):
 import quantitative_math as qm
 prior=rows[max(0,i-19):i+1]; hi=max(r["high"] for r in prior); lo=min(r["low"] for r in prior); risk=qm.risk_scale_price(prior,rows[i]["close"],floor_pct=0.001); fut=rows[i+1:i+horizon+1]
 up=any(r["high"]>=hi+.15*risk for r in fut); down=any(r["low"]<=lo-.15*risk for r in fut)
 return 1 if up and down else 2 if up else 0 if down else 1
