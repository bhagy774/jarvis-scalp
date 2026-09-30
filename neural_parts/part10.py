"""Part 10 owned model: candle-state transition and streak evidence."""
from .common import candle_math, clip
FEATURE_NAMES=("latest_body_fraction","body_acceleration","directional_streak_fraction","transition_rate","green_fraction16","range_scale_pct","return1_robust_z","return4_robust_z","return16_robust_z","drawdown_from_peak","volume_surprise_robust_z","recent_volume_share")
MODEL_SPEC={"task":"candle_transition","dims":(12,12,6,3),"acts":("relu","tanh","linear"),"labels":("reversal","indecision","continuation"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); rows=s["rows"]; vols=[r["volume"] for r in rows]; recent=sum(vols[-4:])/max(sum(vols[-32:]),1e-12)
 vals=(s["candle"]["body_fraction"],s["body_acceleration"],s["directional_streak_fraction"],s["transition_rate"],s["green_fraction"],s["range_scale_pct"],s["ret1_z"],s["ret4_z"],s["ret16_z"],s["drawdown_from_peak"],s["volume_surprise_z"],recent)
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"candle_transition":prediction,"reversal_score_uncalibrated":scores[0],"continuation_score_uncalibrated":scores[2]}
def label_target(rows,i,horizon,neutral_bps,x):
 body=rows[i]["close"]-rows[i]["open"]; ret=rows[i+horizon]["close"]/rows[i]["close"]-1
 if not body or abs(ret)<neutral_bps/10000:return 1
 return 0 if ret*body<0 else 2
