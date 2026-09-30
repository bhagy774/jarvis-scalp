"""Shared data coercion and mathematical primitives, not Part model logic."""
import math
from collections.abc import Mapping

TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h")
PART_NAMES = tuple(f"part{i}_" + name for i, name in enumerate((
    "breakout", "zone", "psychology", "volume", "ml", "trend",
    "volatility", "structure", "orderflow", "candlestats"), 1))


def clip(value, limit=10.0):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non_finite_feature")
    return max(-limit, min(limit, value))


def div(a, b, eps=1e-12):
    return float(a) / (abs(float(b)) + eps)


def mean(xs):
    return sum(xs) / max(1, len(xs))


def std(xs):
    if not xs:
        return 0.0
    m = mean(xs)
    return math.sqrt(mean([(x - m) ** 2 for x in xs]))


def slope(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    xm, ym = (n - 1) / 2.0, mean(xs)
    return sum((i - xm) * (v - ym) for i, v in enumerate(xs)) / (n * (n*n - 1) / 12.0)


def ema(xs, period):
    if not xs:
        return 0.0
    alpha, value = 2.0 / (period + 1.0), xs[0]
    for item in xs[1:]:
        value = alpha * item + (1.0 - alpha) * value
    return value


def ohlcv_rows(data):
    if isinstance(data, (list, tuple)):
        source = data[-64:]
    elif hasattr(data, "columns") and hasattr(data, "iloc"):
        if not {"open", "high", "low", "close", "volume"}.issubset(set(data.columns)):
            raise ValueError("missing_ohlcv_columns")
        frame = data.tail(64)
        source = [{k: frame[k].iloc[i] for k in ("open", "high", "low", "close", "volume")} for i in range(len(frame))]
    else:
        raise ValueError("invalid_ohlcv_data")
    result = []
    for row in source:
        if not isinstance(row, Mapping):
            raise ValueError("invalid_ohlcv_row")
        values = tuple(float(row[k]) for k in ("open", "high", "low", "close", "volume"))
        if not all(math.isfinite(v) for v in values):
            raise ValueError("non_finite_ohlcv")
        o, h, l, c, v = values
        if min(o, h, l, c) <= 0 or v < 0 or h < max(o, c, l) or l > min(o, c, h):
            raise ValueError("invalid_ohlcv")
        result.append({"open": o, "high": h, "low": l, "close": c, "volume": v})
    if len(result) < 64:
        raise ValueError("insufficient_closed_candles")
    return result


def candle_math(data):
    """Return shared rolling primitives; Parts own the actual projections/heads."""
    rows = ohlcv_rows(data)
    op, hi, lo, cl, vol = ([r[k] for r in rows] for k in ("open", "high", "low", "close", "volume"))
    n, price = len(cl), cl[-1]
    ranges = [max(h-l, 1e-12) for h, l in zip(hi, lo)]
    body = [(c-o)/r for c,o,r in zip(cl,op,ranges)]
    upper = [(h-max(o,c))/r for h,o,c,r in zip(hi,op,cl,ranges)]
    lower = [(min(o,c)-l)/r for l,o,c,r in zip(lo,op,cl,ranges)]
    rets = [cl[i]/cl[i-1]-1.0 for i in range(1,n)]
    logc = [math.log(x) for x in cl]
    ret = lambda k: cl[-1]/cl[max(0,n-1-k)]-1.0
    pos = lambda w: div(price-min(lo[-w:]),max(hi[-w:])-min(lo[-w:]))
    highgap = lambda w: div(price-max(hi[-w:]),price)
    lowgap = lambda w: div(price-min(lo[-w:]),price)
    atr14, atr50 = mean(ranges[-14:]), mean(ranges[-50:])
    volmean, volstd = mean(vol[-32:]), std(vol[-32:])
    flow = [b*v for b,v in zip(body,vol)]
    signed_flow = lambda w: div(sum(flow[-w:]),sum(vol[-w:]))
    ema8, ema21, ema50 = (ema(cl[-50:], p) for p in (8,21,50))
    weighted_center = div(sum(c*v for c,v in zip(cl[-32:],vol[-32:])),sum(vol[-32:]))
    profile_low, profile_high = min(lo[-32:]), max(hi[-32:])
    width = max(profile_high-profile_low,1e-12)
    bins=[0.0]*20
    for h,l,c,v in zip(hi[-32:],lo[-32:],cl[-32:],vol[-32:]):
        idx=min(19,max(0,int((((h+l+c)/3.0)-profile_low)/width*20)))
        bins[idx]+=v
    node=(max(range(20),key=bins.__getitem__)+.5)/20.0 if sum(bins)>0 else pos(32)
    transitions=sum(body[i]*body[i+1]<0 for i in range(-16,-1))/15.0
    streak=1
    for i in range(n-2,max(-1,n-9),-1):
        if body[i]==0 or body[i]*body[-1]<=0: break
        streak+=1
    ups=sum(max(hi[i]-hi[i-1],0.0) for i in range(n-14,n))
    downs=sum(max(lo[i-1]-lo[i],0.0) for i in range(n-14,n))
    flow12, ret16 = signed_flow(12), ret(16)
    ret8std, ret32std = std(rets[-8:]),std(rets[-32:])
    rsi_changes=[cl[i]-cl[i-1] for i in range(max(1,n-14),n)]
    gains=mean([max(x,0.0) for x in rsi_changes]); losses=mean([max(-x,0.0) for x in rsi_changes])
    rsi=1.0 if losses==0 and gains else 0.0 if losses==0 else gains/(gains+losses)
    return {"rows":rows,"open":op,"high":hi,"low":lo,"close":cl,"volume":vol,"range":ranges,
        "body":body,"upper":upper,"lower":lower,"returns":rets,"log_close":logc,"ret":ret,"pos":pos,
        "highgap":highgap,"lowgap":lowgap,"atr14":atr14,"atr50":atr50,"atr_pct":div(atr14,price),
        "range_atr":div(ranges[-1],atr14),"ret8std":ret8std,"ret32std":ret32std,"vol_ratio":div(ret8std,ret32std),
        "volmean32":volmean,"volz":div(vol[-1]-volmean,volstd),"volume_ratio":div(vol[-1],volmean),
        "flow":flow,"signed_flow":signed_flow,"flow4":signed_flow(4),"flow12":flow12,
        "ema821":div(ema8-ema21,price),"ema2150":div(ema21-ema50,price),"slope16":slope(logc[-16:]),
        "slope32":slope(logc[-32:]),"ret1":ret(1),"ret4":ret(4),"ret16":ret16,
        "break_hi20":div(cl[-1]-max(hi[-21:-1]),price),"break_lo20":div(cl[-1]-min(lo[-21:-1]),price),
        "break_hi50":div(cl[-1]-max(hi[-51:-1]),price),"break_lo50":div(cl[-1]-min(lo[-51:-1]),price),
        "weighted_dev":div(price-weighted_center,price),"volume_node_pos":node,
        "voltrend":slope([math.log1p(v) for v in vol[-16:]]),
        "flow_ret_div":flow12-max(-1.0,min(1.0,ret16*100.0)),"flow_price_div":flow12-ret16*100.0,
        "transition":transitions,"streak":(streak-1)/7.0,"green_fraction":sum(x>0 for x in body[-16:])/16.0,
        "drawdown16":div(price-max(hi[-16:]),price),"range_pos32":pos(32),"range_pos20":pos(20),"range_pos50":pos(50),
        "range_expansion":div(mean(ranges[-5:]),mean(ranges[-20:])),"close_location":2*div(cl[-1]-lo[-1],ranges[-1])-1,
        "body_ratio":abs(body[-1]),"wick_imbalance":upper[-1]-lower[-1],"ema_rsi":rsi-.5,
        "up_move14":div(ups,price),"down_move14":div(downs,price),"directional_imbalance":div(ups-downs,ups+downs),
        "profile_concentration":div(sum(vol[-4:]),sum(vol[-32:])),"prior_close":cl[-2]}


def mtf_signal_matrix(data):
    frames=data.get("frames") if isinstance(data,Mapping) and isinstance(data.get("frames"),Mapping) else data
    if not isinstance(frames,Mapping) or set(frames)!=set(TIMEFRAMES):
        raise ValueError("incomplete_eight_frame_evidence")
    matrix=[]
    for tf in TIMEFRAMES:
        frame=frames[tf]
        if not isinstance(frame,Mapping): raise ValueError("invalid_frame_evidence")
        values=[]
        for part in PART_NAMES:
            result=frame.get(part)
            if not isinstance(result,Mapping): raise ValueError("missing_part_evidence")
            if result.get("timeframe") and str(result["timeframe"])!=tf: raise ValueError("evidence_timeframe_mismatch")
            raw=result.get("signal",0.0)
            if isinstance(raw,(list,tuple)): raw=raw[-1] if raw else 0.0
            try: value=float(raw)
            except (TypeError,ValueError,OverflowError) as exc: raise ValueError("invalid_part_signal") from exc
            if not math.isfinite(value): raise ValueError("non_finite_part_signal")
            values.append(max(-1.0,min(1.0,value)))
        matrix.append(tuple(values))
    return tuple(matrix)
