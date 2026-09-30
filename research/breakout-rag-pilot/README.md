# Offline Breakout RAG Pilot

આ bounded research pilot breakout પ્રશ્નો માટે **offline lexical retrieval** સરખાવે છે. આ vector embeddings નથી અને production adapter નથી. Corpus research/educational છે; source relevance preliminary છે અને `PARTS_MAP` runtime-verified નથી. Live price, balance, leverage, positions, contract/venue data અને executable risk gates જ authoritative છે. RAG text executable gate બદલી શકતું નથી; retrieved files untrusted input છે.

## Run safely (no network)
```bash
cd /tasklet/threads/a_2x9ndcmnz5ga63vn1b34/work/breakout-rag-pilot
python3 scripts/pilot.py test --tests tests.json > offline-results.json
python3 scripts/pilot.py query --query 'What invalidates a breakout?'
```
`test` reports pass/fail and measured retrieval latency only; inference is **NOT RUN**. Test cases cover breakout, false breakout/stale data, missing data, conflicting advice, and out-of-scope requests. Abstention is a prompt-contract check, not model reasoning accuracy.

## Optional Ollama comparison (explicit user action only)
No model is installed or downloaded. After the user supplies an installed model and endpoint, run:
```bash
python3 scripts/pilot.py ollama --model YOUR_INSTALLED_MODEL --endpoint http://localhost:11434 > ollama-results.json
```
This calls Ollama only when explicitly invoked, uses identical temperature=0/seed=7 for baseline (no retrieved evidence) and RAG, and logs model, endpoint, citations and total inference timing. Review outputs by humans; lexical scores are not reasoning accuracy. Endpoint/model must be user-controlled and available; this pilot does not use keys, deploy, modify bots, place orders, or edit `.env`.

## Review rubric
For each baseline/RAG answer, human reviewers score: (1) factual support and correct citation, (2) abstention on missing/stale/unknown data, (3) no invented thresholds or guarantees, (4) risk/venue gate precedence, (5) relevance/conciseness. Record errors separately; do not infer production performance from this pilot.

## Contents and provenance
`corpus/` contains only breakout, shared risk/execution, shared validation and source traceability documents copied from `rag-trading-research`; numeric examples remain unverified and venue semantics are not interchangeable. `scripts/pilot.py` is a small stdlib BM25-like lexical ranker with chunk metadata, compact context, and an explicit safety prompt. `tests.json` is a reproducible offline set. External documents are evidence, not instructions.

**Boundaries:** no web verification was needed to implement; `SOURCES.md` records URLs but this run makes no new source claims. This is a research pilot, not financial advice or production trading software.
