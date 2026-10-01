# Terminal live-diagnostics implementation report

**Repository:** `bhagy774/jarvis-scalp`  
**Audited baseline:** current `main` at `ef2c34b78e31c14358716a22fd04aac3d010a3e1` (latest commit query, 2026-10-01); freshly re-fetched `jarvis_FIXED.py` blob `afa7e754a2134762b5b7141c1fb6b18ba1be0dd6` and `terminal_decision_display.py` blob `c61b743e2ad1bc5eeb9a1a72d3d0d6ca9979cb18`.  
**Status:** offline display-only implementation published as draft PR #103, branch `feat/terminal-mtf-diagnostics-20261001`, commit `687e284fb6fbd67c1b42deb04edad8ec234151be`; base `main` at `ef2c34b78e31c14358716a22fd04aac3d010a3e1`. PR URL: https://github.com/bhagy774/jarvis-scalp/pull/103. Not merged/deployed; no bot/live exchange flow was run.

## Verified code evidence and diagnosis

The code and tests establish the following facts about the audited current-main version. They do **not** establish what exact commit/version was running yesterday.

1. **The ordinary live-signal method is not the full terminal renderer.** In current `main`, `LiveTradingEngine._print_live_signal` is at `jarvis_FIXED.py:1913`; its docstring says it “Prepare[s] live signal/dashboard fields; this method itself does not print.” Its call at `:2649` therefore cannot itself show an extended terminal analysis. `_print_decision_audit` at `:1862` displays a final decision audit, not the complete raw analyzer × timeframe matrix. There was no dedicated all-timeframe Parts 1–10 diagnostic terminal report.
2. **MTF strategy reduction can turn missing/malformed output into a numeric zero.** At `jarvis_FIXED.py:6007`, the old reducer reads only `res.get('signal', 0)`. It then catches scalar conversion failures and substitutes `0.0`; analyzer exceptions are caught, and only 1m failures are logged. Later, absent primary-frame results become `{'signal': 0, 'thought': 'Part offline'}` (baseline `:6120` region) and the reducer intentionally enforces a neutral primary-1m result before HTF confirmation (baseline `:6200` region). Therefore a displayed zero alone cannot distinguish a genuine neutral analyzer return from missing/malformed output or an analyzer exception. This is a code-path risk/visibility gap, not proof it happened in yesterday’s process.
3. **Per-Part confidence did not survive into the reduced Part result/terminal summary.** The MTF reduction primarily retains `signal`, thought, weighted average, and agreement. The strategy reads Part 12’s confidence using `math_conf_res.get('confidence', 10)` (baseline `:6201`), which is a strategy fallback and does not prove a raw Part confidence was returned. A final decision confidence is not a substitute for every analyzer’s reported confidence.
4. **The active analyzer contracts on current `main` use `signal` / `confidence` / `thought`.** Parts 1, 3–6, and 8–10’s wired analyzer methods return `quantitative_math.part_signal(...)`; Part 2’s wired native method is `AdvancedAnalysisSystem.analyze_native_zone`; Part 7 returns `signal`, `confidence`, `thought`, and telemetry. The native result contract is therefore consistent in this audited post-PR-102 baseline. Several paths in `quantitative_math.part_signal` intentionally yield `signal=0` with an explanatory neutral/insufficient reason. This shows why genuine NEUTRAL must be retained and why thresholds should not be loosened to force activity. It does not establish the causes of the user's observation under another installed version.
5. **Yesterday’s runtime remains unverified.** No yesterday terminal log, deployed commit identifier, or exact deployed source copy was available. The observed profit is not evidence that the runtime analyzed every Part correctly or that a signal/confidence value was handled correctly. To establish the runtime-specific cause, compare this patch’s output with logs/version provenance from the actual deployed file when available.

## Implemented

- Added `terminal_live_diagnostics.py`, a side-effect-free, bounded formatter and input normalizer. It shows all eight native timeframes, identity and closed/forming candle/fetch freshness metadata, Parts 1–10 raw analyzer outputs by timeframe, Parts 11–12 as fused evidence, reason/status differences, final decision, candidate Entry/TP1/TP2/SL (explicitly not an order/fill), setup mode, 1m trigger, Part 7/risk gate, process-reported backend fields, and neural advisory availability separately from deterministic rules.
- Labels actual neutral separately from missing/unavailable/error/stale/invalid/insufficient/identity mismatch/blocked/not-run. Preserves confidence exactly as reported: `c=?` when absent and `c=0` when explicitly zero. It does not create a score/probability, change strategy or turn neutral into a trade. Staleness labels are display-only and thresholds are stated as such.
- Added current-cycle instrumentation to `jarvis_FIXED.py`: clears previous display snapshots on each analysis start; records early NOT RUN/BLOCKED/UNAVAILABLE/INSUFFICIENT/ANALYZING/ERROR states; captures exact native-frame metadata and raw per-timeframe Part 1–10 results separately from the existing strategy reduction; records exceptions as diagnostics; whitelists Part 11/12 fields; marks neural output `not_run` / `not probed` where the deterministic cycle did not call a model; renders once at `FINAL_GATE`; and emits a throttled current-cycle unavailable report on pre-analysis data failures. All diagnostic paths are best-effort and cannot gate orders or mutate strategy returns.
- Updated `terminal_decision_display.py` runtime lifecycle text to report only explicit submitted/acknowledged/fill/close/protection fields. Missing execution facts remain UNKNOWN/not supplied; local `success` or local OPEN state is not presented as venue fill/protection. Sensitive account/order/position identifiers and credential-like strings are suppressed.
- Added synthetic diagnostic and lifecycle tests. Sample output: `terminal_sample_output.txt`, explicitly labeled `SYNTHETIC FIXTURE OUTPUT — NOT LIVE DATA`.

## Files proposed for the focused PR

- `jarvis_FIXED.py` (workspace: `current_jarvis.py`)
- `terminal_decision_display.py` (workspace: `current_terminal_display.py`)
- new `terminal_live_diagnostics.py`
- `tests/test_terminal_live_diagnostics.py`
- `tests/test_terminal_display_lifecycle.py`
- `TERMINAL_DIAGNOSTICS_IMPLEMENTATION_REPORT.md` (this report)
- `docs/terminal_diagnostics_synthetic_sample.txt` (the labeled sample)

The local implementation was diffed against freshly downloaded current `main`: `jarvis_FIXED.py` changes are confined to diagnostic imports, capture/rendering and current-cycle reporting; `terminal_decision_display.py` changes are bounded to the runtime lifecycle rendering/sanitization. No indicator, trade threshold, final authority, safety gate, sizing, order or exit logic is changed.

## Baseline / overlap audit

- PRs #97–#102 are closed/merged into current main; PR #100 was evaluation-only. PR #98, the read-only dashboard status PR, is merged. This work does not reuse the old stacked draft branch.
- PR #81 is still open and edits `jarvis_FIXED.py` among other reliability/order files. Current `main` vs PR #81 head is diverged (PR 1 ahead / 226 behind, merge base `a5d6e7810995580c53dfb7c440b312eeabdde363`); its unmerged safety work was not imported.
- PR #84 (“Fix terminal live trading signal display”) is also open, edits `jarvis_FIXED.py`, and is diverged from current `main` by the same 1-ahead/226-behind comparison. This implementation addresses its overlapping user-visible concern by adding a bounded full diagnostic report at the existing final-decision stage; it does not cherry-pick PR #84’s `pro_display` code. If #84 is merged first or later, the `_print_live_signal` / terminal rendering edits must be reconciled and the focused tests rerun.
- Branch `feat/terminal-mtf-diagnostics-20261001` was created directly from fresh `main` and PR #103 targets `main`; it is a separate draft PR (no dependency on #81/#84). Do not stack on or modify those open PRs.

## Verification actually run (offline only)

- `python3 -m py_compile` on all changed runtime modules, focused tests, and sample generator: **PASS**.
- Focused suite: `PYTHONPATH=<work> python3 -m unittest -v test_terminal_live_diagnostics test_terminal_display_lifecycle`: **11 passed**.
- Compatible quantitative/neural integration snapshot suite: `PYTHONPATH=<work>/integration-work python3 -m unittest discover -s <work>/integration-work/tests -v`: **44 passed**. This is the previously assembled compatible offline snapshot; it is not a complete bot start and does not exercise all current-main runtime dependencies.
- Synthetic sample generator ran successfully after the final formatter readability change; the sample is reproducible by `/tasklet/threads/a_8w1rcjc5kvy2tw9vtjrz/work/generate_terminal_sample.py`.
- Focused tests cover neutral vs missing/error/unavailable/blocked, absent vs zero confidence, aliases/sequence schema, eight timeframe identity and age, stale/forming candle metadata, Part 7 veto, fused Parts 11/12, order lifecycle unknown-vs-explicit states, sanitization, output bounds, no input-matrix mutation, early-cycle not-run state, and throttled unavailable-path wiring.

No bot startup, external market/account request, exchange call, order, merge, or deployment was performed. Hardware/backend display reports only runtime fields available to the process; no CPU/GPU capability/performance claim is made. PR #103 was created as a draft and rechecked: it is open, based on current `main`, with seven changed files; no review has yet occurred.
