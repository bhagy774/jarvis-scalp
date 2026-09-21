#!/usr/bin/env python3
"""Offline, evidence-producing JARVIS system audit.

This auditor deliberately performs static inspection plus small dependency-free
contract probes.  It never imports ``jarvis_FIXED`` or ``run_all_parts`` and
never opens a network connection in ``--offline`` mode.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import datetime as dt
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tokenize
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass
class Finding:
    check: str
    status: str  # PASS, FAIL, SKIPPED, UNVERIFIED
    severity: str  # info, low, medium, high, critical
    message: str
    evidence: str = ""
    file: str = ""
    line: int | None = None
    category: str = "bug"  # bug, environment, coverage, safety


class Audit:
    def __init__(self, root: pathlib.Path, offline: bool = True):
        self.root = root.resolve()
        self.offline = offline
        self.findings: list[Finding] = []
        self.trees: dict[str, ast.AST] = {}
        self.sources: dict[str, str] = {}
        self.edges: list[dict[str, Any]] = []

    def add(self, check: str, status: str, severity: str, message: str,
            evidence: str = "", file: str = "", line: int | None = None,
            category: str = "bug") -> None:
        self.findings.append(Finding(check, status, severity, message,
                                     evidence, file, line, category))

    def rel(self, p: pathlib.Path) -> str:
        try:
            return str(p.resolve().relative_to(self.root))
        except ValueError:
            return str(p)

    def py_files(self) -> list[pathlib.Path]:
        return sorted(p for p in self.root.rglob("*.py")
                      if ".git" not in p.parts and "__pycache__" not in p.parts)

    def parse(self) -> None:
        for path in self.py_files():
            rel = self.rel(path)
            try:
                # tokenize.open honors an encoding cookie without executing code.
                with tokenize.open(path) as fh:
                    source = fh.read()
                self.sources[rel] = source
                self.trees[rel] = ast.parse(source, filename=rel)
            except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
                line = getattr(exc, "lineno", None)
                self.add("syntax", "FAIL", "high", f"Cannot parse Python: {exc}",
                         file=rel, line=line, category="bug")
        parsed = len(self.trees)
        failed = len(self.sources) - parsed
        if failed:
            self.add("syntax", "FAIL", "high",
                     f"{failed} Python file(s) have syntax/encoding errors")
        else:
            self.add("syntax", "PASS", "info",
                     f"Parsed {parsed} Python files without executing application code")

    def local_modules(self) -> set[str]:
        return {pathlib.Path(rel).stem for rel in self.sources
                if pathlib.Path(rel).parent == pathlib.Path(".")}

    def imports(self) -> None:
        local = self.local_modules()
        unresolved: list[tuple[str, int, str]] = []
        unavailable: list[tuple[str, int, str]] = []
        for rel, tree in self.trees.items():
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".")[0]]
                for name in names:
                    if name in local:
                        continue
                    # Repository naming is intentionally conservative: modules
                    # in the jarvis_/part* namespace are expected to be local;
                    # other names are third-party and may be absent here.
                    optional_adapter = name in {"jarvis_rust", "part1_main", "part2_zones", "part_ai"}
                    expected_local = (name.startswith("jarvis_") or name.endswith("_FIXED") or name in {"trading_config", "run_all_parts"}) and not optional_adapter
                    if expected_local:
                        unresolved.append((rel, node.lineno, name))
                        continue
                    try:
                        present = importlib.util.find_spec(name) is not None
                    except (ImportError, ModuleNotFoundError, ValueError):
                        present = False
                    if not present and name not in sys.builtin_module_names:
                        unavailable.append((rel, node.lineno, name))
        # Local imports are checked as a graph: missing local module is a real
        # wiring error; third-party availability varies by audit environment.
        if unresolved:
            for rel, line, name in unresolved:
                self.add("import-wiring", "FAIL", "high",
                         f"Local module {name!r} is not present", f"import {name}", rel, line)
        else:
            self.add("import-wiring", "PASS", "info",
                     "No missing repository-local imports found")
        # Do not turn workstation dependency availability into a code failure.
        names = sorted({n for _, _, n in unavailable})
        if names:
            self.add("dependency-availability", "SKIPPED", "medium",
                     "Optional/external imports unavailable in this audit environment",
                     ", ".join(names), category="environment")
        else:
            self.add("dependency-availability", "PASS", "info",
                     "All statically referenced external imports are available")

    def call_graph(self) -> None:
        defs: dict[str, list[tuple[str, int]]] = {}
        for rel, tree in self.trees.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    defs.setdefault(node.name, []).append((rel, node.lineno))
        for rel, tree in self.trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                if fn in defs:
                    self.edges.append({"caller_file": rel, "caller_line": node.lineno,
                                       "callee": fn, "definitions": defs[fn]})
        main = self.trees.get("jarvis_FIXED.py")
        if main is None:
            self.add("entrypoint", "FAIL", "critical", "jarvis_FIXED.py is missing")
        else:
            names = {n.name: n.lineno for n in ast.walk(main)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            if "main" not in names:
                self.add("entrypoint", "FAIL", "critical", "jarvis_FIXED.py has no main()",
                         file="jarvis_FIXED.py")
            else:
                self.add("entrypoint", "PASS", "info",
                         "Audited entrypoint is jarvis_FIXED.py (not run_all_parts.py)",
                         f"def main(): line {names['main']}", "jarvis_FIXED.py", names["main"])
            guards = [n for n in ast.walk(main) if isinstance(n, ast.If)]
            has_guard = any(isinstance(n.test, ast.Compare) and
                            isinstance(n.test.left, ast.Name) and n.test.left.id == "__name__"
                            for n in guards)
            if not has_guard:
                self.add("entrypoint-guard", "UNVERIFIED", "medium",
                         "jarvis_FIXED.py has no conventional __main__ guard",
                         category="coverage")
            else:
                self.add("entrypoint-guard", "PASS", "info", "Entrypoint guard is present")
        # Evidence that the external Part1-12 runner is not the selected main.
        run = self.sources.get("run_all_parts.py", "")
        if run:
            self.add("runner-distinction", "PASS", "info",
                     "run_all_parts.py is treated as a separate legacy/external runner",
                     "It is not used as the audit entrypoint", "run_all_parts.py")

    def evidence(self, label: str, patterns: Iterable[str], files: Iterable[str] | None = None,
                 status: str = "PASS", severity: str = "info") -> None:
        selected = files or self.sources.keys()
        hits: list[tuple[str, int, str]] = []
        for rel in selected:
            text = self.sources.get(rel, "")
            for i, line in enumerate(text.splitlines(), 1):
                if any(re.search(p, line, re.I) for p in patterns):
                    hits.append((rel, i, line.strip()[:240]))
        if hits:
            evidence = "\n".join(f"{f}:{n}: {line}" for f, n, line in hits[:12])
            self.add(label, status, severity, f"Found {len(hits)} code-referenced evidence line(s)", evidence, category="coverage" if status != "PASS" else "bug")
        else:
            self.add(label, "UNVERIFIED", "medium", "No code evidence matched; runtime wiring remains unverified", category="coverage")

    def static_safety(self) -> None:
        main = self.sources.get("jarvis_FIXED.py", "")
        if main:
            # These are evidence only, not proof that a live action is safe.
            self.evidence("data-acquisition", [r"class DeltaWebSocketClient", r"requests\.", r"websockets", r"fetch.*candle"], ["jarvis_FIXED.py", "binance_data.py", "delta_api_wrapper.py", "upstox_data.py"])
            self.evidence("symbol-selection-locking", [r"selected.*symbol", r"symbol.*lock", r"coin.*scan", r"lock.*symbol", r"symbol_lock"], ["jarvis_FIXED.py", "jarvis_coin_scanner.py", "jarvis_market_router.py"])
            self.evidence("normalization-indicators", [r"class Part[1-9]|class Part1[0-4]|indicator|normalize|feature"], ["jarvis_FIXED.py"])
            self.evidence("fusion-final-veto", [r"build_final_decision|blocking_reasons|gate_reason|SafetyRiskBrain|execution_allowed"], ["jarvis_FIXED.py", "jarvis_decision.py", "oracle_trade_gate.py"])
            self.evidence("risk-contract-lots", [r"calculate_trade_size|MAX_LEVERAGE_CAP|contract_value|enforce_entry_lots|lot_size"], ["jarvis_FIXED.py", "jarvis_risk.py", "jarvis_lot_limits.py", "jarvis_live_trader.py"])
            self.evidence("execution-close-reconciliation", [r"place.*order|create_order|reduce_only|close|reconcile|paper_trad"], ["jarvis_FIXED.py", "jarvis_live_trader.py", "jarvis_close_coordinator.py", "jarvis_position_manager.py"])
            self.evidence("ollama-error-boundary", [r"ollama|validate_decision|snapshot_usable|timeout|except"], ["jarvis_FIXED.py", "jarvis_ollama_context.py", "ollama_integration.py"])
        # Static token presence is explicitly not a safety proof.
        self.add("static-proof-boundary", "PASS", "info",
                 "Static evidence is reported as wiring evidence only; token presence is not safety proof")
        for name, pats in {
            "secrets-scan": [r"(?i)(api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]\s*['\"](?!['\"])[^'\"]+"],
        }.items():
            hits: list[str] = []
            for rel, text in self.sources.items():
                # Never inspect .env files; redact every matched value before report.
                if pathlib.Path(rel).name.startswith(".env"):
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if re.search(pats[0], line):
                        # Redact only the value associated with a secret-like
                        # key, including unquoted values; never emit originals.
                        safe = re.sub(
                            r"(?i)((?:api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]\s*)([\"']?)([^\"'\s,#;]+)\2",
                            r"\1\2[REDACTED]\2", line.strip())
                        hits.append(f"{rel}:{i}: {safe[:240]}")
            if hits:
                self.add(name, "SKIPPED", "medium", "Potential secret-like assignments found; values redacted and not validated", "\n".join(hits[:20]), category="coverage")
            else:
                self.add(name, "PASS", "info", "No non-empty secret-like assignment found in scanned source")

    def probe(self, check: str, code: str, severity: str = "high") -> None:
        # Isolated subprocess: no application entrypoint, no credentials, and a
        # network guard that turns accidental I/O into an explicit failure.
        guard = """
import socket
_real_socket = socket.socket
class BlockedSocket:
    def __init__(self, *a, **k): raise RuntimeError('OFFLINE_NETWORK_BLOCKED')
socket.socket = BlockedSocket
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('OFFLINE_NETWORK_BLOCKED'))
"""
        script = guard + "\nimport sys; sys.path.insert(0, %r)\n" % str(self.root) + code
        try:
            cp = subprocess.run([sys.executable, "-I", "-c", script], cwd=self.root,
                                capture_output=True, text=True, timeout=15,
                                env={"PYTHONHASHSEED": "0", "JARVIS_AUDIT_OFFLINE": "1"})
        except subprocess.TimeoutExpired:
            self.add(check, "FAIL", severity, "Contract probe timed out", category="bug")
            return
        if cp.returncode == 0:
            self.add(check, "PASS", "info", "Offline behavioral contract passed", cp.stdout[-1000:])
        else:
            msg = (cp.stderr or cp.stdout).strip()
            # Do not include arbitrary subprocess output: it could contain a secret.
            msg = re.sub(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S+", r"\1=[REDACTED]", msg)
            match = re.search(r'File "[^"]*/repo/([^" ]+)", line (\d+)', msg)
            evidence_file = match.group(1) if match else ""
            evidence_line = int(match.group(2)) if match else None
            self.add(check, "FAIL", severity, "Offline behavioral contract failed", msg[-2000:], evidence_file, evidence_line, category="bug")

    def behavioral(self) -> None:
        if "jarvis_decision.py" in self.sources:
            self.probe("decision-veto-confidence", """
from jarvis_decision import normalize_confidence, build_final_decision
assert normalize_confidence('85/100 (Autonomy)') == 85
assert normalize_confidence('N/A') is None
r = build_final_decision({'direction':'BUY', 'confidence':85}, symbol='BTCUSDT', blocking_reasons=['risk veto'])
assert r['direction'] == 'NO_TRADE' and r['execution_allowed'] is False
r = build_final_decision({'direction':'BUY', 'confidence':85}, symbol='BTCUSDT', opinions=[{'direction':'BUY'}, {'direction':'SELL'}])
assert r['direction'] == 'NO_TRADE' and r['execution_allowed'] is False
# Both percent and plain numeric text are production input forms and must not throw.
assert build_final_decision({'direction':'BUY', 'confidence':'85%'}, symbol='BTCUSDT')['confidence'] == 85
assert build_final_decision({'direction':'BUY', 'confidence':'85'}, symbol='BTCUSDT')['confidence'] == 85
""")
        else:
            self.add("decision-veto-confidence", "SKIPPED", "high", "Decision helper absent", category="environment")
        if "jarvis_risk.py" in self.sources and "jarvis_lot_limits.py" in self.sources:
            self.probe("risk-sizing-lot-metadata", """
from jarvis_risk import calculate_trade_size
from jarvis_lot_limits import enforce_entry_lots
r = calculate_trade_size(1000, 80, 1, contract_value_usdt=10, require_contract_value=True)
assert r['ok'] and r['contracts'] > 0 and r['contracts'] * r['contract_value_usdt'] <= r['notional_usdt']
q = enforce_entry_lots(12, metadata={'contract_size':5}, available_balance=1000)
assert q == 10 and q % 5 == 0
""")
        else:
            self.add("risk-sizing-lot-metadata", "SKIPPED", "high", "Risk/lot helpers absent", category="environment")
        if "jarvis_position_ownership.py" in self.sources and "jarvis_close_coordinator.py" in self.sources:
            self.probe("close-idempotency-ownership", """
from jarvis_position_ownership import clear_registry, claim_position, claim_close
from jarvis_close_coordinator import claim_close as cclaim, release_close, reconcile_close
clear_registry()
assert claim_position('p','owner-a') is True
assert claim_position('p','owner-b') is False
assert claim_close('p', owner='owner-a')[0] is True
assert claim_close('p', owner='owner-b')[0] is False
assert cclaim('BTCUSDT','p','owner-a') is True
assert cclaim('BTCUSDT','p','owner-b') is False
class MismatchExchange:
    def get_open_positions(self, symbol):
        return [{'symbol':'ETHUSDT', 'size':0}]
assert reconcile_close(MismatchExchange(), 'BTCUSDT', 'SELL', 1)['ambiguous'] is True
class PartialExchange:
    def get_open_positions(self, symbol):
        return [{'symbol':'BTCUSDT', 'size':1}]
assert reconcile_close(PartialExchange(), 'BTCUSDT', 'SELL', 1)['ambiguous'] is True
release_close('BTCUSDT','p', force=True)
""")
        else:
            self.add("close-idempotency-ownership", "SKIPPED", "high", "Ownership/close helpers absent", category="environment")
        if "jarvis_ollama_context.py" in self.sources:
            self.probe("ollama-error-boundary", """
from jarvis_ollama_context import validate_decision, snapshot_usable, build_snapshot
assert validate_decision(None)[0] is None
assert validate_decision({'direction':'BUY', 'confidence':'not-a-score'})[0] is None
valid, err = validate_decision({'decision':'WAIT', 'confidence':0, 'rationale':'no trade', 'plan':{}})
assert valid and err is None
s = build_snapshot(symbol='BTCUSDT', timestamp=None, current_price=100, market_context={'symbol':'BTCUSDT'}, part_results={})
assert snapshot_usable(s)[0] is True
stale = build_snapshot(symbol='BTCUSDT', timestamp='2000-01-01T00:00:00+00:00', current_price=float('nan'), market_context={'symbol':'BTCUSDT'}, part_results={})
assert snapshot_usable(stale)[0] is False and stale['market']['price'] is None
mismatch = build_snapshot(symbol='BTCUSDT', timestamp=None, current_price=100, market_context={'symbol':'ETHUSDT'}, part_results={})
assert snapshot_usable(mismatch)[0] is False
""", severity="medium")
        else:
            self.add("ollama-error-boundary", "SKIPPED", "medium", "Ollama context helper absent", category="environment")
        rust = self.root / "jarvis_rust"
        if rust.exists() and (rust / "Cargo.toml").exists():
            self.add("rust-optional-parity", "SKIPPED", "medium",
                     "Rust source is present but parity/build comparison is not run by the offline Python audit",
                     "Manual/CI cargo parity test required", "jarvis_rust", category="coverage")
        else:
            self.add("rust-optional-parity", "UNVERIFIED", "medium",
                     "No Rust implementation detected", category="coverage")
        # These checks are intentionally static/coverage checks and not a claim
        # that paper/live execution is safe.
        for check, files, pats in [
            ("paper-isolation", ["jarvis_FIXED.py", "jarvis_live_trader.py"], [r"PAPER_CONFIG", r"paper", r"reduce_only"]),
            ("restart-reconciliation", ["jarvis_FIXED.py", "jarvis_live_trader.py", "jarvis_position_manager.py"], [r"load.*trade|read.*json|reconcile|restart|persist"]),
        ]:
            self.evidence(check, pats, files)

    def report(self) -> dict[str, Any]:
        counts = {s: sum(1 for f in self.findings if f.status == s)
                  for s in ("PASS", "FAIL", "SKIPPED", "UNVERIFIED")}
        return {
            "schema": "jarvis-offline-audit/v1",
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "root": str(self.root), "offline": self.offline,
            "entrypoint": "jarvis_FIXED.py",
            "counts": counts,
            "failure_exit": counts["FAIL"] > 0,
            "findings": [asdict(f) for f in self.findings],
            "call_graph_edges": self.edges[:1000],
            "limitations": [
                "No main application module or external service was imported.",
                "No live feeds, orders, credentials, or arbitrary repository tests were run.",
                "Static matches identify code evidence but do not prove runtime wiring or safety.",
                "Optional dependencies, dynamic imports, generated code, and Rust parity may remain unverified.",
            ],
        }


def markdown(report: dict[str, Any]) -> str:
    lines = ["# JARVIS offline full-system audit", "", f"- Entrypoint: `{report['entrypoint']}`",
             f"- Offline: `{report['offline']}`", f"- Generated: `{report['generated_at']}`",
             f"- Counts: " + ", ".join(f"{k}={v}" for k, v in report["counts"].items()), "",
             "## Findings", "", "| Status | Severity | Check | Message | Evidence |", "|---|---|---|---|---|"]
    for f in report["findings"]:
        ev = (f.get("evidence") or "").replace("\n", "<br>").replace("|", "\\|")[:700]
        lines.append(f"| {f['status']} | {f['severity']} | `{f['check']}` | {f['message']} | `{ev}` |")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {x}" for x in report["limitations"])
    lines += ["", "## Exit semantics", "", "The command exits nonzero only when a reproducible `FAIL` finding is present. `SKIPPED` and `UNVERIFIED` are never silently counted as passes."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="required safe mode; no application imports/network")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", default="audit_report.json")
    ap.add_argument("--markdown", default="audit_report.md")
    args = ap.parse_args(argv)
    if not args.offline:
        print("Refusing to run without --offline; this auditor is intentionally offline-only.", file=sys.stderr)
        return 2
    os.environ["JARVIS_AUDIT_OFFLINE"] = "1"
    audit = Audit(pathlib.Path(args.root), offline=True)
    audit.parse(); audit.imports(); audit.call_graph(); audit.static_safety(); audit.behavioral()
    report = audit.report()
    pathlib.Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pathlib.Path(args.markdown).write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "json": args.json, "markdown": args.markdown}, sort_keys=True))
    return 1 if report["failure_exit"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
