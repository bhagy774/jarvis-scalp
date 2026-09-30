"""Part 6 model: local-linear trend state and return-sign persistence."""
from .common import candle_math, clip
FEATURE_NAMES=("robust_trend_score","state_velocity_z","theil_sen_slope_robust_z","sign_persistence","directional_coherence","directional_streak_fraction","change_point_bic_gain","range_position32","break_high20_risk_scale","break_low20_risk_scale","realized_vol","jump_variation_share")
MODEL_SPEC={"task":"trend_persistence","dims":(12,12,4,1),"acts":("tanh","relu","linear"),"labels":("trend_break","trend_persists"),"kind":"sigmoid"}
def prepare_features(data):
 s=candle_math(data)
 vals=(s["trend_score"],s["state_velocity_z"],s["theil_sen_slope_z"],s["sign_persistence"],s["directional_coherence"],s["directional_streak_fraction"],s["change_point_bic_gain"],s["range_position_32"],s["break_high20_scale"],s["break_low20_scale"],s["realized_vol"],s["jump_share"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"trend_persistence":prediction,"trend_persistence_score_uncalibrated":scores[1]}
def label_target(rows,i,horizon,neutral_bps,x):
 directional=x[0]+x[1]+x[2]
 if abs(directional)<1e-7:return 0
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1
 return int(abs(ret)>=neutral_bps/10000 and ret*directional>0)
