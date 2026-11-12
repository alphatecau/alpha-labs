# TradingAgents v0.7.1 — Alpha Labs Phase 1–2 gap audit (research-only)

Upstream: TauricResearch/TradingAgents release v0.7.1, tag c454491 (27 Oct 2026).
Scope: narrow, additive safety guards and deterministic tests. This is NOT a full repository-wide proof.

## Inspected Alpha Labs paths (main at branch creation)
- `data/csv_import.py`: rejects nonfinite OHLCV, duplicate/unordered timestamps, irregular intervals, invalid OHLC and naive timestamps; hashes source CSV. Existing protections retained.
- `data/adapters/kraken_ohlc.py`: explicitly excludes last forming candle, validates through CSV importer and records source/CSV hashes. Existing protections retained.
- `backtest/costs.py`: models fee/slippage but lacks explicit finite-value validation in constructor (follow-up integration required).
- `tests/unit/test_research_foundation.py`: covers next-bar entry, deterministic replay, adverse costs, and provenance.

## Added standalone guards
- Calendar-date normalisation and publication-time eligibility to prevent future filings entering historical decisions.
- Explicit complete-candle eligibility at a decision timestamp.
- Finite Decimal portfolio accounting with strict canonical symbol matching; no implicit symbol guesses.
- SHA256 source binding and explicit provenance.
- Adversarial tests for all of the above.

## Not yet integrated / must not be claimed solved
- Guard invocation from every research entry point, SEC/fundamental provider, settlement loop, portfolio loader or promotion gate.
- Long exchange holiday settlement; last settlement-pass error propagation; run-ID collision prevention; report overwrite cleanup; decision-date memory ordering.
- Account/broker symbol normalisation requires an authoritative mapping and venue metadata.
- Historical publication-time reconstruction and third-party price authenticity.
- CI result, strategy profitability, broker execution, or deployment readiness until independently verified.

## Next verification
Run `python -m unittest discover -s tests/unit -p 'test_tradingagents_071_guards.py' -v` with package installed; then the full Python CI suite. Integrate guards only after auditing call sites. No trading/deployment authorised.
