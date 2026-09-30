"""Part 9 owned model: follow-through from close-location OHLCV proxy only."""
from .common import candle_math, clip
FEATURE_NAMES=("flow_proxy4","flow_proxy12","flow_return_divergence","flow_proxy_slope12","return4_robust_z","return16_robust_z","volume_surprise_robust_z","recent_volume_share","range_scale_pct","latest_body_signed","flow_price_divergence","flow_proxy_dispersion")
MODEL_SPEC={"task":"flow_followthrough","dims":(12,14,5,1),"acts":("tanh","relu","linear"),"labels":("flow_diverges","flow_followthrough"),"kind":"sigmoid"}
def _flow_series(rows):
 out=[]
 for r in rows:
  span=max(r["high"]-r["low"],r["close"]*1e-12)
  out.append(max(-1.,min(1.,(2*r["close"]-r["high"]-r["low"])/span)))
 return out
def _slope(xs):
 n=len(xs)
 if n<2:return 0.
 xm=(n-1)/2; ym=sum(xs)/n
 return sum((i-xm)*(x-ym) for i,x in enumerate(xs))/(n*(n*n-1)/12)
def prepare_features(data):
 s=candle_math(data); rows=s["rows"]; loc=_flow_series(rows); r4=loc[-4:]; r12=loc[-12:]; flow4=sum(r4)/max(1,len(r4)); flow12=sum(r12)/max(1,len(r12)); vols=[r["volume"] for r in rows]; base=sum(vols[-32:]); recent=sum(vols[-4:])/max(base,1e-12); dispersion=(sum((v-flow12)**2 for v in r12)/max(1,len(r12)))**.5
 vals=(flow4,flow12,flow12-s["ret16_z"]/5,_slope(r12),s["ret4_z"],s["ret16_z"],s["volume_surprise_z"],recent,s["range_scale_pct"],s["candle"]["body_signed"],s["flow_trend_divergence"],dispersion)
 return tuple(clip(x) for x in vals)
def interpret_scores(scores,prediction): return {"flow_followthrough":prediction,"followthrough_score_uncalibrated":scores[1],"flow_source":"close-location OHLCV proxy; not exchange tape/order-book"}
def label_target(rows,i,horizon,neutral_bps,x):
 flow=float(x[0]+x[1])
 if abs(flow)<.02:return None
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1
 return int(abs(ret)>=neutral_bps/10000 and ret*flow>0)
