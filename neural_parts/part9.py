"""Part 9 owned model: OHLCV signed-flow follow-through head."""
from .common import candle_math, clip
FEATURE_NAMES=("signed_flow4","signed_flow12","flow_return_divergence","cvd_slope12","ret4","ret16","volume_z","volume_ratio","range_atr","body_signed","flow_price_divergence","atr14_pct")
MODEL_SPEC={"task":"flow_followthrough","dims":(12,14,5,1),"acts":("tanh","relu","linear"),"labels":("flow_diverges","flow_followthrough"),"kind":"sigmoid"}
def prepare_features(data):
 s=candle_math(data); vals=(s["flow4"],s["flow12"],s["flow_ret_div"],slope(s["flow"][-12:]),s["ret4"],s["ret16"],s["volz"],s["volume_ratio"],s["range_atr"],s["body"][-1],s["flow_price_div"],s["atr_pct"])
 return tuple(clip(x) for x in vals)
def slope(xs):
 n=len(xs); xm=(n-1)/2; ym=sum(xs)/n
 return sum((i-xm)*(x-ym) for i,x in enumerate(xs))/(n*(n*n-1)/12) if n>1 else 0.0
def interpret_scores(scores,prediction): return {"flow_followthrough":prediction,"followthrough_score_uncalibrated":scores[1]}
def label_target(rows,i,horizon,neutral_bps,x):
 flow=x[0]+x[1]
 if abs(flow)<.02:return None
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1
 return int(abs(ret)>=neutral_bps/10000 and ret*flow>0)
