from jarvis_options_context import apply_options_confirmation, resolve_options_context


class Delta:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
    def get_institutional_bias(self, asset):
        self.calls.append(asset)
        return self.responses.get(asset, {"bias": "NEUTRAL", "score": 0})


def intel(bias, score=3):
    return {"bias": bias, "score": score, "pcr": 0.8, "reasons": ["chain signal"]}


def test_selected_asset_chain_is_primary_not_btc():
    d = Delta({"ETH": intel("BULLISH"), "BTC": intel("BEARISH")})
    result = resolve_options_context(d, "ETHUSDT")
    assert result.role == "asset_primary"
    assert result.source_asset == "ETH"
    assert d.calls == ["ETH"]


def test_btc_is_macro_only_when_alt_chain_is_unavailable():
    d = Delta({"SOL": {"bias": "NEUTRAL", "score": 0}, "BTC": intel("BULLISH")})
    result = resolve_options_context(d, "SOLUSDT")
    assert result.role == "btc_macro_confirmation"
    assert result.selected_asset == "SOL"
    assert result.source_asset == "BTC"
    assert d.calls == ["SOL", "BTC"]


def test_btc_macro_has_smaller_bounded_effect_than_primary():
    d = Delta({"SOL": {"bias": "NEUTRAL", "score": 0}, "BTC": intel("BULLISH")})
    fallback = resolve_options_context(d, "SOLUSDT")
    assert apply_options_confirmation("CALL", 70, fallback)[0] == 72
    own = resolve_options_context(Delta({"SOL": intel("BULLISH")}), "SOLUSDT")
    assert apply_options_confirmation("CALL", 70, own)[0] == 74


def test_btc_never_becomes_the_altcoin_contract_or_strike_source():
    d = Delta({"ETH": {"bias": "NEUTRAL", "score": 0}, "BTC": intel("BEARISH")})
    result = resolve_options_context(d, "ETHUSDT")
    assert result.selected_asset == "ETH"
    assert result.role == "btc_macro_confirmation"
    adjusted, note = apply_options_confirmation("CALL", 70, result)
    assert adjusted == 66
    assert "BTC" in note
