"""Part 7 model: future realized/downside-variance expansion evidence, not a gate."""
from .common import candle_math, clip
import math
FEATURE_NAMES=("realized_volatility","downside_realized_volatility","jump_variation_share","range_scale_pct","high_variance_state_posterior","short_long_realized_vol_ratio","tail_downside_risk_scale","tail_upside_risk_scale","body_anomaly_robust_z","state_innovation_z","change_point_bic_gain","volume_surprise_robust_z")
MODEL_SPEC={"task":"future_volatility_regime","dims":(12,16,8,3),"acts":("relu","tanh","linear"),"labels":("contracting","normal","expanding"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data)
 vals=(s["realized_vol"],s["downside_vol"],s["jump_share"],s["range_scale_pct"],s["high_state_posterior"],s["short_long_realized_vol_ratio"],s["tail_downside_scale"],s["tail_upside_scale"],s["body_robust_z"],s["state_innovation_z"],s["change_point_bic_gain"],s["volume_surprise_z"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"future_volatility_regime":prediction,"expansion_score_uncalibrated":scores[2],"contraction_score_uncalibrated":scores[0]}
def label_target(rows,i,horizon,neutral_bps,x):
 past=[math.log(rows[j]["close"]/rows[j-1]["close"]) for j in range(max(1,i-31),i+1)]; future=[math.log(rows[j]["close"]/rows[j-1]["close"]) for j in range(i+1,i+horizon+1)]
 def sd(a):
  m=sum(a)/max(1,len(a)); return math.sqrt(sum((v-m)**2 for v in a)/max(1,len(a)))
 ratio=sd(future)/max(sd(past),1e-12)
 return 0 if ratio<.75 else 2 if ratio>1.25 else 1
