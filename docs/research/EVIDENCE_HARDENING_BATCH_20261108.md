# Alpha Labs — Evidence hardening batch (8 November 2026)

**Branch:** `research/strategy-evidence-gates-v1` — draft PR #15. **Live trading disabled.**

## Completed engineering changes
1. Confirmed previous commit `f457e44` passed 141 offline research tests and Sites CI.
2. Added independent reconciliation fixtures for zero-order flat markets and trending markets under 0/0, 10/10 and 35/75 bps fee/slippage assumptions. These are synthetic tests; they do not prove real-world execution economics.
3. Added checks for valid SHA-256 source digest format, nonempty declared provenance and hourly candle interval. A valid hash is **not** independent market-price authentication.
4. Added a declared `--tested-strategies` parameter. When multiple strategies were examined, assessment records `MULTIPLE_COMPARISON_CORRECTION_NOT_APPLIED`; it does not falsely adjust or approve a strategy.
5. Expanded JSON assessment output with each input file's SHA-256 and byte count, declared dataset hashes and code revisions, assumed period-cost stress, and explicit `promotion_authorised=false` and `strategy_profitable_verified=false`.

## Example
```sh
export PYTHONPATH=packages/alpha_lab/src
python -m alpha_lab.research.assessment_cli evidence-fold-001.json evidence-fold-002.json \
  --output assessment.json --additional-cost-per-period 0.0002 --tested-strategies 6
```

This CLI is **not** an independent OOS seal, executable-fill test, broker connectivity or production promotion gate.

## Release conditions
- Confirm CI for the latest commit, including all new edge-case tests.
- Review modelled fee and NAV parity against historical source archives.
- Run and independently reproduce genuine BTCUSDT/ETHUSDT/SOLUSDT archive-backed reports.
- Preserve draft PR and trading-disabled status pending explicit approval.
