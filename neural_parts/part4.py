"""Part 4 model: volume surprise, proxy flow and range-overlap distribution."""
from .common import candle_math, clip
FEATURE_NAMES=("volume_surprise_robust_z","ohlcv_flow_imbalance_proxy","flow_trend_divergence","close_location_in_value_area","poc_distance_risk_scale","volume_concentration4_32","return1_robust_z","return4_robust_z","change_point_bic_gain","sign_persistence","range_scale_pct","downside_realized_vol")
MODEL_SPEC={"task":"volume_confirmed_move","dims":(12,18,8,3),"acts":("relu","relu","linear"),"labels":("sell_confirmed","unconfirmed","buy_confirmed"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data)
 vals=(s["volume_surprise_z"],s["flow_proxy"],s["flow_trend_divergence"],s["close_location_in_value"],s["poc_distance_scale"],s["volume_concentration_4_32"],s["ret1_z"],s["ret4_z"],s["change_point_bic_gain"],s["sign_persistence"],s["range_scale_pct"],s["downside_vol"])
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"volume_confirmation":prediction,"sell_confirmed_score_uncalibrated":scores[0],"buy_confirmed_score_uncalibrated":scores[2]}
def label_target(rows,i,horizon,neutral_bps,x):
 future=rows[i+1:i+horizon+1]; ret=rows[i+horizon]["close"]/rows[i]["close"]-1; base=sum(r["volume"] for r in rows[max(0,i-31):i+1])/len(rows[max(0,i-31):i+1]); fvol=sum(r["volume"] for r in future)/len(future)
 if fvol<base*1.05 or abs(ret)<neutral_bps/10000:return 1
 return 2 if ret>0 else 0
