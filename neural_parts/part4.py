"""Part 4 owned model: signed-volume confirmation head."""
from .common import candle_math, clip
FEATURE_NAMES=("volume_z","volume_ratio","signed_flow12","signed_flow4","flow_return_divergence","volume_trend","ret1","ret4","range_atr","close_location","volume_concentration","atr14_pct")
MODEL_SPEC={"task":"volume_confirmed_move","dims":(12,18,8,3),"acts":("relu","relu","linear"),"labels":("sell_confirmed","unconfirmed","buy_confirmed"),"kind":"softmax"}
def prepare_features(data):
 s=candle_math(data); vals=(s["volz"],s["volume_ratio"],s["flow12"],s["flow4"],s["flow_ret_div"],s["voltrend"],s["ret1"],s["ret4"],s["range_atr"],s["close_location"],s["profile_concentration"],s["atr_pct"])
 return tuple(clip(x) for x in vals)
def label_target(rows,i,horizon,neutral_bps,x):
 future=rows[i+1:i+horizon+1]; ret=rows[i+horizon]["close"]/rows[i]["close"]-1; base=sum(r["volume"] for r in rows[max(0,i-31):i+1])/len(rows[max(0,i-31):i+1]); fvol=sum(r["volume"] for r in future)/len(future)
 if fvol<base*1.05 or abs(ret)<neutral_bps/10000:return 1
 return 2 if ret>0 else 0
