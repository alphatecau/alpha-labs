# Alpha Labs — Week 1 isolated risk-replay implementation and limits

**Date:** 2026-11-08. **Scope:** draft PR #15 development branch only.
**Deployment / merge / live execution:** not authorised and not performed.

## Engineering changes
- Added `research/breakout_risk_replay.py`, a separate offline-only replay that preserves the legacy engine for comparison. Uses prior completed 4h ATR, next-hour-open entry, a 3x ATR protective stop, hourly-low trigger approximation, conservative open-gap stop execution and after-close trailing updates.
- Entry sizing is bounded by modelled worst-case planned loss including fee/slippage at the modelled stop (0.25% of starting equity), a 20% allocation cap and available cash. One position per independent single-market run; no leverage.
- Blocks new entries when a 2% UTC daily loss or 5% portfolio peak drawdown threshold is reached. These are **entry suspensions**, not guaranteed liquidation or full independent risk-authority enforcement. Cross-asset aggregate risk (1%) cannot be validated by separate per-symbol simulations.
- Added `research/breakout_reconcile.py`: independent sequential order-ledger reconstruction of modelled fees, cash, position quantity and every hourly liquidation NAV, with failure on tampering.
- Wired the risk-constrained result and independent reconciliation into `breakout_evaluation.py` while preserving the old diagnostic for comparability.
- Added synthetic tests for no-trade, planned risk, intrabar stop, adverse gap, fee/NAV tampering, missing candles and same-hour reentry.
- Added an archive-verified three-market cost-stress runner, 10/10, 20/20 and 40/40 bps fee/slippage per side.

## Material limitations
1. **CI and tests:** committed but not independently run or confirmed for the latest branch head in this session. GitHub commit workflow-run lookup and combined-status lookup returned empty collections. User's earlier confirmation applied to an older commit.
2. **Market data:** no archive dataset is available in this connected session; real-market runs have not been executed.
3. **OHLC ambiguity:** hourly high/low cannot establish tick order or actual stop execution; stop fills, adverse slippage and fees remain assumptions. Gap-through-stop can exceed planned risk.
4. **Risk controls:** single-market replay, not an independently authorised multi-market portfolio risk engine. No daily forced liquidation, no global aggregate stop-risk accounting, no cross-venue spreads/impact or exchange-specific tick/lot rules.
5. **Strategy semantics:** the predeclared 4h signal and separate 1h protective stop can yield earlier exits than the original close-only candidate. Report both versions; do not quietly substitute one for the other in preregistered statistical tests.
6. **Statistical validation:** no independently sealed forward holdout, new walk-forward result, confidence interval or profitability proof.

## Next mandatory acceptance evidence
- GitHub Actions passing on current branch head, with the full unit-test logs.
- Independently reproduced risk replay, including planned loss cap and gap-loss exceedance cases.
- Verified BTCUSDT, ETHUSDT and SOLUSDT monthly archives and source manifests.
- Reconciled 1x/2x/4x cost-stress reports and explicit cross-asset aggregation tests.
- Frozen walk-forward split and independent holdout boundary before results are viewed.

**Decision:** engineering safeguards improved; **NO-GO** for strategy promotion or live execution.
