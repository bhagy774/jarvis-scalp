from concurrent.futures import ThreadPoolExecutor
import json
import threading

import pytest

from jarvis_multicoin_execution import (
    CandidateRejected, DeterministicPaperAdapter, PortfolioCoordinator,
    candidate_from_analysis,
)


NOW = 1_800_000_000.0
POLICIES = {"BTC": "btc-paper-v1", "ETH": "eth-paper-v1", "SOL": "sol-paper-v1"}


def analysis(symbol="BTCUSDT", product_id="101", *, plan=None, status="COMPLETE", fetched=NOW-10, completed=NOW-2):
    asset = symbol
    for quote in ("USDT", "USD"):
        if asset.endswith(quote):
            asset = asset[:-len(quote)]
            break
    return {
        "status": status, "scope": "parts1-12-analysis-only", "analysis_only": True,
        "decision_authority": "none", "execution_eligible": False,
        "request_identity": {"venue": "delta", "market_type": "perpetual", "instrument_id": product_id, "symbol": symbol},
        "snapshot_version": "snap-abc", "snapshot_fetched_at": fetched,
        "analysis_completed_at": completed, "freshness_status": "FRESH",
        "execution_plan": plan if plan is not None else {
            "timeframe": "5m", "decision_timestamp": NOW-3, "reference_price_timestamp": NOW-3,
            "reference_price": 100.0, "max_slippage_pct": 0.1, "max_chase_pct": 0.25,
            "direction": "BUY", "entry_price": 100.0, "stop_loss": 98.0, "take_profit": 105.0,
            "quantity": 1.0, "size_unit": "base_asset_quantity",
            "sizing_provenance": "fixture-risk-engine-v1", "risk_notional": 2.0,
            "policy_id": POLICIES.get(asset),
        },
    }


def candidate(symbol="BTCUSDT", product_id="101", **kwargs):
    return candidate_from_analysis(analysis(symbol, product_id, **kwargs), policy_registry=POLICIES, now=NOW)


class Adapter(DeterministicPaperAdapter):
    def __init__(self, status="FILLED", *, fail=False, authoritative=True, quantity=1.0):
        self.status, self.fail, self.authoritative, self.quantity = status, fail, authoritative, quantity
        self.submissions, self.closes = [], []

    def submit(self, cand, idempotency_key):
        self.submissions.append((cand.candidate_id, idempotency_key))
        if self.fail:
            raise TimeoutError("simulated timeout after submit attempt")
        return {"status": self.status, "order_id": "order-" + idempotency_key[:8],
                "authoritative": self.authoritative, "filled_quantity": self.quantity}

    def close(self, candidate_id, identity, quantity):
        self.closes.append((candidate_id, identity, quantity))
        return {"status": "CLOSE_PENDING", "authoritative": False}


def coordinator(tmp_path, **kwargs):
    return PortfolioCoordinator(journal_path=str(tmp_path / "ledger.json"), enabled=True,
                                max_positions=kwargs.pop("max_positions", 3),
                                max_total_notional=kwargs.pop("max_total_notional", 1000),
                                max_total_risk=kwargs.pop("max_total_risk", 100), **kwargs)


def test_candidate_contract_requires_all_explicit_fields_and_asset_policy():
    good = candidate()
    assert good.direction == "BUY" and good.identity.instrument_id == "101"
    assert good.notional == 100.0 and good.risk_notional == 2.0
    for bad_result, policies in [
        (analysis(status="PARTIAL"), POLICIES),
        ({**analysis(), "snapshot_fetched_at": NOW-500}, POLICIES),
        ({**analysis(), "execution_plan": None}, POLICIES),
        ({**analysis(), "request_identity": {"venue": "delta", "symbol": "BTCUSDT"}}, POLICIES),
        (analysis(plan={**analysis()["execution_plan"], "direction": "NO TRADE"}), POLICIES),
        (analysis(plan={**analysis()["execution_plan"], "quantity": None}), POLICIES),
        (analysis(plan={**analysis()["execution_plan"], "stop_loss": 101}), POLICIES),
        (analysis(plan={k: v for k, v in analysis()["execution_plan"].items() if k != "reference_price"}), POLICIES),
        (analysis(plan={**analysis()["execution_plan"], "entry_price": 101.0}), POLICIES),
        (analysis(), {"BTC": "different-policy"}),
    ]:
        with pytest.raises(CandidateRejected):
            candidate_from_analysis(bad_result, policy_registry=policies, now=NOW)


def test_concurrent_competing_signals_reserve_atomically_and_are_idempotent(tmp_path):
    c = coordinator(tmp_path, max_positions=1)
    a, b = candidate("BTCUSDT", "101"), candidate("ETHUSDT", "202")
    adapter = Adapter()
    barrier = threading.Barrier(2)
    def submit(item):
        barrier.wait()
        return c.submit(item, adapter)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, (a, b)))
    assert sorted(r["status"] for r in results) == ["BLOCKED", "FILLED"]
    winner = a if results[0]["status"] == "FILLED" else b
    assert c.submit(winner, adapter)["duplicate"] is True
    assert len(adapter.submissions) == 1


def test_correlation_cap_and_full_identity_isolation(tmp_path):
    c = coordinator(tmp_path, max_positions=4, correlation_groups={"BTC": "majors", "ETH": "majors"}, max_per_correlation_group=1)
    one = candidate("BTCUSDT", "101")
    # Same ticker on another product is not a distinct concurrent position.
    same_symbol_different_id = candidate("BTCUSDT", "102")
    other = candidate("SOLUSDT", "303")
    adapter = Adapter()
    assert c.submit(one, adapter)["status"] == "FILLED"
    assert c.submit(same_symbol_different_id, adapter)["status"] == "BLOCKED"
    assert c.submit(candidate("ETHUSDT", "202"), adapter)["status"] == "BLOCKED"
    assert c.submit(other, adapter)["status"] == "FILLED"


def test_risk_budget_is_reserved_atomically_in_addition_to_notional(tmp_path):
    c = coordinator(tmp_path, max_positions=5, max_total_risk=2.0)
    adapter = Adapter()
    assert c.submit(candidate("BTCUSDT", "101"), adapter)["status"] == "FILLED"
    assert c.submit(candidate("ETHUSDT", "202"), adapter)["status"] == "BLOCKED"


def test_timeout_unknown_and_partial_fill_keep_reservation_across_restart(tmp_path):
    path = str(tmp_path / "ledger.json")
    a, b = candidate("BTCUSDT", "101"), candidate("ETHUSDT", "202")
    c = PortfolioCoordinator(journal_path=path, enabled=True, max_positions=1, max_total_notional=1000, max_total_risk=100)
    assert c.submit(a, Adapter(fail=True))["status"] == "SUBMISSION_UNKNOWN"
    reopened = PortfolioCoordinator(journal_path=path, enabled=True, max_positions=1, max_total_notional=1000, max_total_risk=100)
    assert reopened.submit(a, Adapter())["duplicate"] is True
    assert reopened.submit(b, Adapter())["status"] == "BLOCKED"
    # A complete snapshot that does not resolve the submission is not a rejection.
    assert reopened.reconcile({"complete": True, "positions": [], "orders": {}})
    assert reopened.snapshot()["orders"][a.candidate_id]["status"] == "SUBMISSION_UNKNOWN"
    assert reopened.submit(b, Adapter())["status"] == "BLOCKED"

    p = candidate("SOLUSDT", "303")
    c2 = coordinator(tmp_path / "partial", max_positions=1)
    assert c2.submit(p, Adapter(status="PARTIAL", quantity=0.4))["status"] == "PARTIAL"
    assert c2.reconcile({"complete": True,
                          "positions": [{**p.identity.to_dict(), "notional": p.entry_price*0.4, "risk_notional": 0.8}],
                          "orders": {p.candidate_id: {"status": "PARTIAL", "authoritative": True, "filled_quantity": 0.4}}})
    assert c2.snapshot()["orders"][p.candidate_id]["status"] == "PARTIAL"


def test_account_snapshot_mismatch_preserves_owned_position_state(tmp_path):
    c = coordinator(tmp_path)
    p = candidate()
    c.submit(p, Adapter())
    before = c.snapshot()
    assert not c.reconcile({"complete": True, "positions": [],
                            "orders": {p.candidate_id: {"status": "FILLED", "authoritative": True}}})
    assert c.snapshot()["orders"][p.candidate_id]["status"] == before["orders"][p.candidate_id]["status"] == "FILLED"
    assert not c.reconcile({"complete": False, "positions": [], "orders": {}})
    assert not c.reconcile({"complete": True, "positions": [{"symbol": "BTCUSDT", "notional": 10}], "orders": {}})


def test_rejection_release_only_after_authoritative_reconciliation(tmp_path):
    c = coordinator(tmp_path, max_positions=1)
    p, other = candidate(), candidate("ETHUSDT", "202")
    assert c.submit(p, Adapter(status="REJECTED", authoritative=True))["status"] == "SUBMISSION_UNKNOWN"
    assert c.submit(other, Adapter())["status"] == "BLOCKED"
    assert c.reconcile({"complete": True, "positions": [],
                        "orders": {p.candidate_id: {"status": "REJECTED", "authoritative": True}}})
    assert c.snapshot()["orders"][p.candidate_id]["status"] == "REJECTED"
    assert c.submit(other, Adapter())["status"] == "FILLED"


def test_owned_position_close_is_per_identity_and_reconciled_not_assumed(tmp_path):
    c = coordinator(tmp_path, max_positions=2)
    first, second = candidate("BTCUSDT", "101"), candidate("SOLUSDT", "303")
    adapter = Adapter()
    c.submit(first, adapter); c.submit(second, adapter)
    assert c.close_position(first.candidate_id, second.identity.to_dict(), adapter)["status"] == "BLOCKED"
    assert c.close_position(first.candidate_id, first.identity.to_dict(), adapter)["status"] == "CLOSE_PENDING"
    assert c.snapshot()["orders"][second.candidate_id]["status"] == "FILLED"
    assert not c.reconcile({"complete": True, "positions": [{**first.identity.to_dict(), "notional": 100, "risk_notional": 2}],
                            "orders": {first.candidate_id: {"status": "CLOSED", "authoritative": True}}})
    assert c.snapshot()["orders"][first.candidate_id]["status"] == "CLOSE_PENDING"
    assert c.reconcile({"complete": True, "positions": [{**second.identity.to_dict(), "notional": 100, "risk_notional": 2}],
                        "orders": {first.candidate_id: {"status": "CLOSED", "authoritative": True},
                                   second.candidate_id: {"status": "FILLED", "authoritative": True, "filled_quantity": 1}}})
    assert c.snapshot()["orders"][first.candidate_id]["status"] == "CLOSED"
    assert c.snapshot()["orders"][second.candidate_id]["status"] == "FILLED"


def test_live_engine_paper_handoff_rejects_native_analysis_but_accepts_explicit_plan(tmp_path):
    from unittest.mock import patch
    import jarvis_FIXED as jarvis

    engine = object.__new__(jarvis.LiveTradingEngine)
    engine.multicoin_paper_coordinator = coordinator(tmp_path)
    engine.multicoin_paper_adapter = DeterministicPaperAdapter()
    engine._multicoin_paper_policies = POLICIES
    engine.multicoin_paper_status = {"enabled": True, "submitted": 0, "blocked": 0}
    native_result = analysis(plan=None)
    native_result["execution_plan"] = None
    status = {"results": {"delta|perpetual|101|BTCUSDT": native_result}}
    with patch("jarvis_FIXED.time.time", return_value=NOW):
        engine._consume_multicoin_paper_results(status)
    assert engine.multicoin_paper_status["submitted"] == 0
    assert engine.multicoin_paper_status["last_status"] == "BLOCKED_INVALID_CANDIDATE"

    explicit = analysis()
    status["results"]["delta|perpetual|101|BTCUSDT"] = explicit
    with patch("jarvis_FIXED.time.time", return_value=NOW):
        engine._consume_multicoin_paper_results(status)
    assert engine.multicoin_paper_status["submitted"] == 1
    assert engine.multicoin_paper_status["last_status"] == "FILLED"
    assert len(engine.multicoin_paper_coordinator.snapshot()["orders"]) == 1


def test_bad_journal_fails_closed_and_disabled_coordinator_never_submits(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text('{broken')
    c = PortfolioCoordinator(journal_path=str(path), enabled=True, max_total_notional=1000, max_total_risk=100)
    assert c.healthy is False and c.submit(candidate(), Adapter())["status"] == "BLOCKED"
    disabled = PortfolioCoordinator(journal_path=str(tmp_path / "disabled.json"), enabled=False, max_total_notional=1000, max_total_risk=100)
    assert disabled.submit(candidate(), Adapter())["status"] == "BLOCKED"
