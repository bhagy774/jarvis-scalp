"""Part 3 model: robust candle-body, auction-location and anomaly evidence."""
from .common import candle_math, clip
FEATURE_NAMES=("body_fraction","upper_wick_fraction","lower_wick_fraction","auction_close_location","body_anomaly_robust_z","body_change","return1_robust_z","return4_robust_z","range_scale_pct","state_innovation_z","volume_surprise_robust_z","opening_gap_risk_scale")
MODEL_SPEC={"task":"candle_reversal","dims":(12,10,4,1),"acts":("tanh","relu","linear"),"labels":("no_reversal","reversal"),"kind":"sigmoid"}
def prepare_features(data):
 s=candle_math(data); g=s["candle"]; rows=s["rows"]
 gap=(rows[-1]["open"]-rows[-2]["close"])/s["range_scale_price"]
 vals=(g["body_fraction"],g["upper_wick"],g["lower_wick"],g["close_location"],s["body_robust_z"],s["body_acceleration"],s["ret1_z"],s["ret4_z"],s["range_scale_pct"],s["state_innovation_z"],s["volume_surprise_z"],gap)
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"candle_reversal":prediction,"reversal_score_uncalibrated":scores[1]}
def label_target(rows,i,horizon,neutral_bps,x):
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1; body=rows[i]["close"]-rows[i]["open"]
 return int(bool(body and abs(ret)>=neutral_bps/10000 and ret*body<0))
