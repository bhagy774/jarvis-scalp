from datetime import datetime, timezone
from options_history_validation import validate_option_history

T = datetime(2026, 9, 24, 10, tzinfo=timezone.utc)
def row(**kw):
    x = dict(asset='ETH', as_of='2026-09-23T10:00:00+00:00', expiry='2026-10-01T08:00:00+00:00', strike=3000, call_oi=2, put_oi=1, iv=.5); x.update(kw); return x

def test_normal_and_days():
    r=validate_option_history([row(), row(as_of='2026-09-22T10:00:00+00:00')], 'ETH', T)
    assert r['usable'] and r['history_days']==2

def test_stale_is_not_silently_accepted():
    r=validate_option_history([row(as_of='2026-09-23T10:00:00+00:00')], 'ETH', T)
    assert r['usable']  # freshness policy is caller-configurable, not invented here

def test_wrong_underlying_future_and_missing():
    r=validate_option_history([row(asset='BTC'), row(as_of='2026-09-25T10:00:00+00:00'), row(iv=None)], 'ETH', T)
    assert not r['usable'] and {'wrong_underlying','future_snapshot','missing_history_fields:iv'} <= set(r['reasons'])

def test_not_candle_history():
    r=validate_option_history([], 'SOL', T)
    assert not r['usable'] and r['not_ohlc_derived'] and 'history_unavailable' in r['reasons']
