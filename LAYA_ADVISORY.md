# Experimental Laya advisory integration

This change adds `jarvis_laya_advisor.py`, a lazy optional bridge to the upstream `laya.Router` API (`Router().predict(state, questions)`). It proposes one of BUY/SELL/NO_TRADE for a caller-supplied, same-symbol snapshot. `Advisory.deterministic_decision` is carried through unchanged; the result is commentary and must not be consumed as approval, sizing, risk, position ownership, or order instruction. Missing dependency, invalid/mismatched input, timeout, and runtime failure are returned as visibly distinct statuses, never as a confirmation. It does not perform orders or alter algorithm output.

Enable/status: `JARVIS_LAYA_ADVISORY=true` (default); set false to disable. Install optional package with `python -m pip install laya`. The first real prediction may download a checkpoint; no download/inference was performed in this PR. General-purpose Laya is **not trained or validated for markets** and outputs are experimental only. Do not enable in live-trading critical paths absent domain validation.

This initial integration is a tested adapter only: existing Ollama call sites in `jarvis_FIXED.py`, parts, and options have NOT been replaced/wired. Existing Ollama-dependent execution gate behavior remains unchanged; this PR makes no claim of complete Ollama replacement. This limitation is explicit to avoid weakening deterministic entry/risk/ownership/close/sizing guards or inadvertently changing decisions. Follow-up must wire advisory display paths only, independently verify that the pure-algorithm guard remains untouched, and remove/rework legacy model call sites under dedicated tests.

Offline tests: `python -m unittest test_jarvis_laya_advisor.py` (no Laya package/model/network required).
