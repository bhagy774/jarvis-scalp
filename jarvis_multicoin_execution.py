"""Fail-closed multicoin candidate validation and paper execution lifecycle.

No exchange implementation lives here. Candidate conversion requires an
explicit plan, an external allow-listed asset policy, and a fresh COMPLETE
Parts 1-12 result. The coordinator is thread-atomic and persists a conservative
journal before submission; UNKNOWN/PARTIAL/FILLED exposure retains its entire
reservation until a complete authoritative reconciliation proves a terminal
state. Default disabled.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Tuple


class CandidateRejected(ValueError):
    pass


@dataclass(frozen=True, order=True)
class FullIdentity:
    venue: str
    market_type: str
    instrument_id: str
    symbol: str

    @classmethod
    def parse(cls, raw: Mapping[str, Any]) -> "FullIdentity":
        if not isinstance(raw, Mapping):
            raise CandidateRejected("full instrument identity required")
        vals = [str(raw.get(k) or "").strip() for k in ("venue", "market_type", "instrument_id", "symbol")]
        if any(not x for x in vals):
            raise CandidateRejected("full instrument identity required")
        return cls(vals[0].lower(), vals[1].lower(), vals[2], vals[3].upper())

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


def _positive_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise CandidateRejected(f"{name} must be explicit numeric data")
    if not math.isfinite(number) or number <= 0:
        raise CandidateRejected(f"{name} must be finite and positive")
    return number


def _nonnegative_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise CandidateRejected(f"{name} must be explicit numeric data")
    if not math.isfinite(number) or number < 0:
        raise CandidateRejected(f"{name} must be finite and non-negative")
    return number


def _base_asset(symbol: str) -> str:
    for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[:-len(quote)]
    raise CandidateRejected("symbol has no recognized quote suffix")


@dataclass(frozen=True)
class ValidatedCandidate:
    candidate_id: str
    identity: FullIdentity
    timeframe: str
    snapshot_version: str
    snapshot_fetched_at: float
    analysis_completed_at: float
    decision_timestamp: float
    reference_price_timestamp: float
    reference_price: float
    max_slippage_pct: float
    max_chase_pct: float
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    quantity: float
    size_unit: str
    sizing_provenance: str
    policy_id: str
    risk_notional: float

    @property
    def notional(self) -> float:
        return self.entry_price * self.quantity

    def to_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        row["identity"] = self.identity.to_dict()
        return row


def candidate_from_analysis(
    result: Mapping[str, Any], *, policy_registry: Mapping[str, str], now: Optional[float] = None,
    max_age_seconds: float = 180.0,
) -> ValidatedCandidate:
    """Validate one explicitly supplied `execution_plan`; never invent geometry/size.

    `policy_registry` is trusted runtime configuration, not a field trusted from
    the analyzer. Values are exact policy IDs allow-listed per base asset.
    """
    if not isinstance(result, Mapping) or result.get("status") != "COMPLETE":
        raise CandidateRejected("only COMPLETE analysis can produce a candidate")
    if (result.get("scope") != "parts1-12-analysis-only" or result.get("analysis_only") is not True
            or result.get("decision_authority") != "none" or result.get("execution_eligible") is not False):
        raise CandidateRejected("unexpected analysis scope/authority")
    if result.get("freshness_status") not in (None, "FRESH"):
        raise CandidateRejected("analysis result is stale")
    identity = FullIdentity.parse(result.get("request_identity"))
    snapshot_version = str(result.get("snapshot_version") or "").strip()
    if not snapshot_version:
        raise CandidateRejected("snapshot version missing")
    try:
        fetched = float(result["snapshot_fetched_at"])
        completed = float(result["analysis_completed_at"])
    except (KeyError, TypeError, ValueError, OverflowError):
        raise CandidateRejected("analysis timestamps missing")
    current = time.time() if now is None else float(now)
    if not all(math.isfinite(t) for t in (fetched, completed, current)) or fetched > completed or completed > current + 2:
        raise CandidateRejected("analysis timestamps invalid")
    if current - fetched > max(1.0, float(max_age_seconds)):
        raise CandidateRejected("analysis result expired")
    plan = result.get("execution_plan")
    if not isinstance(plan, Mapping):
        raise CandidateRejected("explicit execution plan missing; no inferred entry/size")
    tf = str(plan.get("timeframe") or "").strip()
    if tf not in {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h"}:
        raise CandidateRejected("unsupported/missing decision timeframe")
    decision_at = _positive_number(plan.get("decision_timestamp"), "decision_timestamp")
    if decision_at < fetched or decision_at > completed + 2 or current - decision_at > max(1.0, float(max_age_seconds)):
        raise CandidateRejected("decision timestamp invalid or stale")
    reference_at = _positive_number(plan.get("reference_price_timestamp"), "reference_price_timestamp")
    if reference_at < fetched or reference_at > completed + 2 or current - reference_at > max(1.0, float(max_age_seconds)):
        raise CandidateRejected("reference price timestamp invalid or stale")
    reference_price = _positive_number(plan.get("reference_price"), "reference_price")
    max_slippage_pct = _nonnegative_number(plan.get("max_slippage_pct"), "max_slippage_pct")
    max_chase_pct = _nonnegative_number(plan.get("max_chase_pct"), "max_chase_pct")
    direction = str(plan.get("direction") or "").strip().upper().replace("-", "_").replace(" ", "_")
    if direction in {"NO_TRADE", "NOTRADE", "HOLD", "NONE"}:
        raise CandidateRejected("NO TRADE is not an executable candidate")
    if direction not in {"BUY", "SELL"}:
        raise CandidateRejected("direction must be BUY or SELL")
    entry = _positive_number(plan.get("entry_price"), "entry_price")
    stop = _positive_number(plan.get("stop_loss"), "stop_loss")
    target = _positive_number(plan.get("take_profit"), "take_profit")
    qty = _positive_number(plan.get("quantity"), "quantity")
    if direction == "BUY" and not stop < entry < target:
        raise CandidateRejected("BUY stop/entry/target geometry invalid")
    if direction == "SELL" and not target < entry < stop:
        raise CandidateRejected("SELL stop/entry/target geometry invalid")
    chase_pct = abs(entry - reference_price) / reference_price * 100.0
    if chase_pct > max_chase_pct:
        raise CandidateRejected("entry exceeds explicit max chase from reference price")
    size_unit = str(plan.get("size_unit") or "").strip().lower()
    provenance = str(plan.get("sizing_provenance") or "").strip()
    if size_unit not in {"base_asset_quantity", "contracts"} or not provenance:
        raise CandidateRejected("explicit size unit and sizing provenance required")
    risk_notional = _positive_number(plan.get("risk_notional"), "risk_notional")
    if risk_notional > abs(entry - stop) * qty + max(1e-8, abs(entry - stop) * qty * 1e-6):
        raise CandidateRejected("declared risk exceeds stop-distance exposure")
    asset = _base_asset(identity.symbol)
    policy_id = str(policy_registry.get(asset) or "").strip()
    if not policy_id or str(plan.get("policy_id") or "").strip() != policy_id:
        raise CandidateRejected("no matching approved per-asset policy")
    raw_id = "|".join((identity.venue, identity.market_type, identity.instrument_id, identity.symbol,
                       tf, snapshot_version, direction, str(decision_at), str(reference_at), str(reference_price),
                       str(max_slippage_pct), str(max_chase_pct), str(entry), str(stop), str(target),
                       str(qty), size_unit, provenance, policy_id, str(risk_notional)))
    candidate_id = hashlib.sha256(raw_id.encode()).hexdigest()
    return ValidatedCandidate(candidate_id, identity, tf, snapshot_version, fetched, completed,
                              decision_at, reference_at, reference_price, max_slippage_pct, max_chase_pct,
                              direction, entry, stop, target, qty, size_unit, provenance, policy_id, risk_notional)


class PaperExecutionAdapter(Protocol):
    def submit(self, candidate: ValidatedCandidate, idempotency_key: str) -> Mapping[str, Any]: ...
    def close(self, candidate_id: str, identity: FullIdentity, quantity: float) -> Mapping[str, Any]: ...


class DeterministicPaperAdapter:
    """No-network paper adapter; assumes exact requested entry (no slippage model)."""
    def submit(self, candidate: ValidatedCandidate, idempotency_key: str) -> Mapping[str, Any]:
        return {"status": "FILLED", "authoritative": True,
                "order_id": "paper-" + idempotency_key[:20],
                "filled_quantity": candidate.quantity, "model": "requested-price-zero-slippage"}

    def close(self, candidate_id: str, identity: FullIdentity, quantity: float) -> Mapping[str, Any]:
        return {"status": "CLOSED", "authoritative": True,
                "order_id": "paper-close-" + str(candidate_id)[:20], "filled_quantity": quantity}


_ACTIVE = {"RESERVED", "SUBMISSION_UNKNOWN", "PARTIAL", "FILLED", "CLOSE_PENDING"}
_TERMINAL = {"REJECTED", "CLOSED"}
_VALID_STATES = _ACTIVE | _TERMINAL


class PortfolioCoordinator:
    """Bounded, lock-serialized paper portfolio with restart-safe journal.

    Submission is deliberately separate from authorization: this coordinator
    accepts only ValidatedCandidate objects and is disabled by default. Orders
    are retained on timeout/unknown, and per-position close never sweeps peers.
    """
    def __init__(self, *, journal_path: str, enabled: bool = False,
                 max_positions: int = 2, max_total_notional: float, max_total_risk: float,
                 per_asset_caps: Optional[Mapping[str, int]] = None,
                 correlation_groups: Optional[Mapping[str, str]] = None,
                 max_per_correlation_group: int = 1, clock: Callable[[], float] = time.time):
        self.enabled = bool(enabled)
        self.journal_path = Path(journal_path)
        self.max_positions = max(1, int(max_positions))
        self.max_total_notional = _positive_number(max_total_notional, "max_total_notional")
        self.max_total_risk = _positive_number(max_total_risk, "max_total_risk")
        self.per_asset_caps = {str(k).upper(): max(1, int(v)) for k, v in (per_asset_caps or {}).items()}
        self.correlation_groups = {str(k).upper(): str(v) for k, v in (correlation_groups or {}).items()}
        self.max_per_correlation_group = max(1, int(max_per_correlation_group))
        self.clock = clock
        self._lock = threading.RLock()
        self.healthy = True
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._external_positions: Dict[str, Dict[str, float]] = {}
        self._load()

    @staticmethod
    def _identity_key(identity: FullIdentity) -> str:
        return "|".join((identity.venue, identity.market_type, identity.instrument_id, identity.symbol))

    def _load(self) -> None:
        try:
            if self.journal_path.exists():
                raw = json.loads(self.journal_path.read_text(encoding="utf-8"))
                if raw.get("schema_version") != 1 or not isinstance(raw.get("orders"), dict) or not isinstance(raw.get("external_positions", {}), dict):
                    raise ValueError("bad journal schema")
                orders = raw["orders"]
                for key, item in orders.items():
                    if not isinstance(item, dict) or item.get("status") not in _VALID_STATES:
                        raise ValueError("bad journal order")
                    if key != item.get("candidate_id") or not isinstance(item.get("candidate"), dict):
                        raise ValueError("bad journal identity")
                    FullIdentity.parse(item["candidate"].get("identity"))
                    _positive_number(item.get("reserved_notional"), "journal reserved notional")
                    _positive_number(item.get("reserved_risk"), "journal reserved risk")
                external = {}
                for key, value in raw.get("external_positions", {}).items():
                    if not isinstance(value, dict):
                        raise ValueError("external position risk/notional required")
                    external[str(key)] = {"notional": _positive_number(value.get("notional"), "external notional"),
                                          "risk_notional": _positive_number(value.get("risk_notional"), "external risk")}
                self._orders, self._external_positions = orders, external
        except Exception:
            # Corrupt state means no orders, no opens, and no new admission.
            self.healthy = False
            self._orders, self._external_positions = {}, {}

    def _save(self) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"schema_version": 1, "orders": self._orders,
                              "external_positions": self._external_positions}, sort_keys=True, separators=(",", ":"))
        fd, tmp = tempfile.mkstemp(prefix=".multicoin-", suffix=".tmp", dir=str(self.journal_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.journal_path)
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass

    def _capacity(self, candidate: ValidatedCandidate) -> bool:
        active = [x for x in self._orders.values() if x["status"] in _ACTIVE]
        external = self._external_positions
        identity_key = self._identity_key(candidate.identity)
        if any(FullIdentity.parse(x["candidate"]["identity"]) == candidate.identity for x in active):
            return False
        if identity_key in external:
            return False
        count = len(active) + len(external)
        total = sum(float(x["reserved_notional"]) for x in active) + sum(float(v["notional"]) for v in external.values())
        risk = sum(float(x["reserved_risk"]) for x in active) + sum(float(v["risk_notional"]) for v in external.values())
        if (count >= self.max_positions or total + candidate.notional > self.max_total_notional
                or risk + candidate.risk_notional > self.max_total_risk):
            return False
        asset = _base_asset(candidate.identity.symbol)
        asset_count = sum(1 for x in active if _base_asset(FullIdentity.parse(x["candidate"]["identity"]).symbol) == asset)
        asset_count += sum(1 for k in external if _base_asset(k.split("|", 3)[-1]) == asset)
        if asset in self.per_asset_caps and asset_count >= self.per_asset_caps[asset]:
            return False
        group = self.correlation_groups.get(asset)
        if group:
            group_count = sum(1 for x in active if self.correlation_groups.get(_base_asset(FullIdentity.parse(x["candidate"]["identity"]).symbol)) == group)
            group_count += sum(1 for k in external if self.correlation_groups.get(_base_asset(k.split("|", 3)[-1])) == group)
            if group_count >= self.max_per_correlation_group:
                return False
        return True

    def submit(self, candidate: ValidatedCandidate, adapter: PaperExecutionAdapter) -> Dict[str, Any]:
        with self._lock:
            if not self.enabled or not self.healthy:
                return {"status": "BLOCKED", "reason": "coordinator disabled or journal unhealthy"}
            old = self._orders.get(candidate.candidate_id)
            if old:
                return {"status": old["status"], "candidate_id": candidate.candidate_id, "duplicate": True}
            if not self._capacity(candidate):
                return {"status": "BLOCKED", "reason": "portfolio/correlation capacity exceeded"}
            row = {"candidate_id": candidate.candidate_id, "candidate": candidate.to_dict(),
                   "status": "RESERVED", "reserved_notional": candidate.notional,
                   "reserved_risk": candidate.risk_notional, "created_at": float(self.clock()), "order_id": None, "close_requested": False}
            self._orders[candidate.candidate_id] = row
            try:
                self._save()  # durable reservation before external side effect
            except Exception:
                self._orders.pop(candidate.candidate_id, None)
                self.healthy = False
                return {"status": "BLOCKED", "reason": "reservation journal write failed"}
            try:
                response = adapter.submit(candidate, candidate.candidate_id)
                if not isinstance(response, Mapping):
                    raise ValueError("malformed adapter response")
            except Exception:
                response = {"status": "SUBMISSION_UNKNOWN", "authoritative": False}
            state = str(response.get("status") or "SUBMISSION_UNKNOWN").upper()
            if state not in {"SUBMISSION_UNKNOWN", "PARTIAL", "FILLED", "REJECTED"}:
                state = "SUBMISSION_UNKNOWN"
            row["status"] = state
            row["order_id"] = str(response.get("order_id") or "") or None
            row["last_response_authoritative"] = response.get("authoritative") is True
            try:
                filled_quantity = float(response.get("filled_quantity", 0.0) or 0.0)
            except (TypeError, ValueError, OverflowError):
                filled_quantity = float("nan")
            if not math.isfinite(filled_quantity) or filled_quantity < 0 or filled_quantity > candidate.quantity:
                state, filled_quantity = "SUBMISSION_UNKNOWN", 0.0
            if state in {"FILLED", "PARTIAL"} and not row["last_response_authoritative"]:
                state = "SUBMISSION_UNKNOWN"
            if state == "FILLED" and filled_quantity < candidate.quantity:
                state = "PARTIAL" if filled_quantity > 0 else "SUBMISSION_UNKNOWN"
            row["filled_quantity"] = filled_quantity
            if state == "REJECTED":
                # Even a submit acknowledgement is not the authoritative account/order
                # reconciliation required to release capacity.
                row["reported_rejection"] = bool(row["last_response_authoritative"])
                row["status"] = "SUBMISSION_UNKNOWN"
            try:
                self._save()
            except Exception:
                self.healthy = False
                row["status"] = "SUBMISSION_UNKNOWN"
            return {"status": row["status"], "candidate_id": candidate.candidate_id, "order_id": row["order_id"]}

    def reconcile(self, snapshot: Mapping[str, Any]) -> bool:
        """Apply only complete full-identity account snapshots and explicit order states."""
        if not isinstance(snapshot, Mapping) or snapshot.get("complete") is not True:
            return False
        positions_raw = snapshot.get("positions")
        orders_raw = snapshot.get("orders")
        if not isinstance(positions_raw, Sequence) or isinstance(positions_raw, (str, bytes)) or not isinstance(orders_raw, Mapping):
            return False
        try:
            as_of = float(snapshot.get("as_of", self.clock()))
            if not math.isfinite(as_of):
                return False
            positions: Dict[str, Dict[str, float]] = {}
            for item in positions_raw:
                identity = FullIdentity.parse(item)
                _base_asset(identity.symbol)
                notional = _positive_number(item.get("notional"), "position notional")
                risk_notional = _positive_number(item.get("risk_notional"), "position risk notional")
                key = self._identity_key(identity)
                if key in positions:
                    return False
                positions[key] = {"notional": notional, "risk_notional": risk_notional}
            order_states = {}
            for cid, detail in orders_raw.items():
                if not isinstance(detail, Mapping) or detail.get("authoritative") is not True:
                    return False
                state = str(detail.get("status") or "").upper()
                if state not in {"SUBMISSION_UNKNOWN", "PARTIAL", "FILLED", "REJECTED", "CLOSED"}:
                    return False
                order_states[str(cid)] = (state, detail)
        except (CandidateRejected, TypeError, ValueError, AttributeError):
            return False
        with self._lock:
            new_orders = json.loads(json.dumps(self._orders))
            for cid, row in new_orders.items():
                identity = FullIdentity.parse(row["candidate"]["identity"])
                ikey = self._identity_key(identity)
                update = order_states.get(cid)
                present = ikey in positions
                if update:
                    state, detail = update
                    if state in {"FILLED", "PARTIAL"} and not present:
                        return False  # account/open-position mismatch: preserve previous ledger
                    if state == "CLOSED" and present:
                        return False
                    if state == "REJECTED" and present:
                        return False
                    row["status"] = state
                    if state == "CLOSED":
                        row["closed_at"] = as_of
                    if "filled_quantity" in detail:
                        quantity = float(detail["filled_quantity"])
                        planned = float(row["candidate"]["quantity"])
                        if not math.isfinite(quantity) or quantity < 0 or quantity > planned:
                            return False
                        if state == "FILLED" and quantity + 1e-9 < planned:
                            return False
                        if state == "PARTIAL" and not 0 < quantity < planned:
                            return False
                        row["filled_quantity"] = quantity
                elif row["status"] in {"FILLED", "PARTIAL", "CLOSE_PENDING"} and not present:
                    # A full snapshot proves closure but does not account for unknown orders.
                    row["status"] = "CLOSED"
                    row["closed_at"] = as_of
                elif row["status"] in {"FILLED", "PARTIAL"} and present:
                    pass
                elif row["status"] == "SUBMISSION_UNKNOWN":
                    pass  # absence does not prove rejection; reservation remains
            local_keys = {self._identity_key(FullIdentity.parse(r["candidate"]["identity"])) for r in new_orders.values() if r["status"] in _ACTIVE}
            external = {key: value for key, value in positions.items() if key not in local_keys}
            old_orders, old_external = self._orders, self._external_positions
            self._orders, self._external_positions = new_orders, external
            try:
                self._save()
            except Exception:
                self._orders, self._external_positions = old_orders, old_external
                self.healthy = False
                return False
            return True

    def close_position(self, candidate_id: str, identity: Mapping[str, Any], adapter: PaperExecutionAdapter) -> Dict[str, Any]:
        with self._lock:
            if not self.enabled or not self.healthy:
                return {"status": "BLOCKED"}
            row = self._orders.get(str(candidate_id))
            if not row or row["status"] not in {"FILLED", "PARTIAL"}:
                return {"status": "BLOCKED", "reason": "position not open/owned"}
            expected = FullIdentity.parse(row["candidate"]["identity"])
            if FullIdentity.parse(identity) != expected:
                return {"status": "BLOCKED", "reason": "position identity mismatch"}
            if row.get("close_requested"):
                return {"status": "CLOSE_PENDING", "duplicate": True}
            previous_status = row["status"]
            row["status"] = "CLOSE_PENDING"
            row["close_requested"] = True
            try:
                self._save()
            except Exception:
                row["status"] = previous_status
                row["close_requested"] = False
                self.healthy = False
                return {"status": "BLOCKED", "reason": "close journal write failed"}
            try:
                response = adapter.close(str(candidate_id), expected, float(row.get("filled_quantity") or 0.0))
                if not isinstance(response, Mapping):
                    raise ValueError("malformed close response")
            except Exception:
                response = {"status": "CLOSE_PENDING"}
            if str(response.get("status", "")).upper() == "REJECTED" and response.get("authoritative") is True:
                row["status"] = "FILLED" if row.get("filled_quantity") else "PARTIAL"
                row["close_requested"] = False
            try:
                self._save()
            except Exception:
                self.healthy = False
                return {"status": "CLOSE_PENDING"}
            return {"status": row["status"], "candidate_id": candidate_id}

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {"enabled": self.enabled, "healthy": self.healthy,
                    "orders": json.loads(json.dumps(self._orders)),
                    "external_positions": dict(self._external_positions)}
