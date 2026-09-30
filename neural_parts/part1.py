"""Part 1 model: normalized range-escape and penalized change-point evidence."""
from .common import candle_math, clip
FEATURE_NAMES=("break_high20_risk_scale","break_low20_risk_scale","range_position20","robust_trend_score","state_velocity_z","change_point_bic_gain","change_point_shift_z","volume_surprise_robust_z","return4_robust_z","return16_robust_z","body_anomaly_robust_z","auction_close_location")
MODEL_SPEC={"task":"first_touch_breakout","dims":(12,20,8,3),"acts":("relu","tanh","linear"),"labels":("bear_break","no_break","bull_break"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); g=s["candle"]
 vals=(s["break_high20_scale"],s["break_low20_scale"],s["range_position_20"],s["trend_score"],s["state_velocity_z"],s["change_point_bic_gain"],s["change_point_shift_z"],s["volume_surprise_z"],s["ret4_z"],s["ret16_z"],s["body_robust_z"],g["close_location"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"breakout_event":prediction,"bull_break_score_uncalibrated":scores[2],"bear_break_score_uncalibrated":scores[0]}
def label_target(rows,i,horizon,neutral_bps,x):
 import quantitative_math as qm
 future=rows[i+1:i+horizon+1]; price=rows[i]["close"]
 scale=qm.risk_scale_price(rows[max(0,i-63):i+1],price,floor_pct=0.001)
 up=price+0.6*scale; down=price-0.6*scale
 for r in future:
  hit_up=r["high"]>=up; hit_down=r["low"]<=down
  if hit_up and hit_down:return 1
  if hit_up:return 2
  if hit_down:return 0
 return 1
