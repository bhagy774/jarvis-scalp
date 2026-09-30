"""Part 5 model: state-space trend, return-change and tail-risk evidence."""
from .common import candle_math, clip
FEATURE_NAMES=("robust_trend_score","state_velocity_z","state_innovation_z","change_point_bic_gain","change_point_shift_z","return1_robust_z","return4_robust_z","return16_robust_z","high_variance_state_posterior","short_long_realized_vol_ratio","downside_realized_vol","tail_downside_risk_scale")
MODEL_SPEC={"task":"forward_return_direction","dims":(12,24,12,3),"acts":("relu","tanh","linear"),"labels":("down_return","neutral_return","up_return"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data)
 vals=(s["trend_score"],s["state_velocity_z"],s["state_innovation_z"],s["change_point_bic_gain"],s["change_point_shift_z"],s["ret1_z"],s["ret4_z"],s["ret16_z"],s["high_state_posterior"],s["short_long_realized_vol_ratio"],s["downside_vol"],s["tail_downside_scale"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"forward_return_bucket":prediction,"down_score_uncalibrated":scores[0],"up_score_uncalibrated":scores[2]}
def label_target(rows,i,horizon,neutral_bps,x):
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1; t=neutral_bps/10000
 return 2 if ret>t else 0 if ret< -t else 1
