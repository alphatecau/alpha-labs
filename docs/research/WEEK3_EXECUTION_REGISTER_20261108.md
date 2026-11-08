# Week 3 execution and verification register

Branch: `research/week3-preregistered-strategy-discovery`, separated from draft PR #15.
Frozen hypothesis protocol: `docs/research/WEEK3_PREREGISTRATION_20261108.md`, committed **before** any Week 3 evaluation code or workflow.

## Completed implementation
- Archived the Week 2 final failure evidence reference (run 42472199571, artifact 13613059109 and its SHA-256) in the preregistration.
- Added three fixed, lagged hypotheses: regime-filtered trend, volatility-adjusted mean reversion and cross-asset rotation.
- Added modelled long/cash portfolio simulator with 20% maximum initial exposure, modelled 0.25% per-entry risk sizing, 3x lagged hourly ATR stop, gap handling, 2% daily suspension, 5% drawdown halt, fees and adverse slippage, and no same-hour reentry after exit.
- Added a separate cash-delta ledger reconstruction. **This is not an independent portfolio-wide risk authoriser**, and does not establish executable fill prices.
- Added 21 asset/strategy/cost combinations × 5 retrospective development folds = 105 simulated fold evaluations.
- Added unit tests for causal signals, portfolio accounting, no-trading flags and invalid target rejection.
- Added research-only GitHub Actions workflow `.github/workflows/week3-research.yml`.

## Unfinished gates (do not claim complete)
- CI has been configured and triggered by the workflow-file commit, but the actual job outcome, full test results and uploaded 21-comparison evidence are **UNVERIFIED** until the run ID/logs/artifact are retrieved.
- Risk-matched passive benchmark and regime-conditional realised P&L are **NOT IMPLEMENTED**; cash benchmark is 0%.
- Portfolio risk authorisation remains **NOT INDEPENDENTLY VERIFIED**. Accounting reconciliation checks cash deltas, not independent position/fee/NAV reconstruction.
- Statistical promotion is impossible with five folds and 21 comparisons. Fold independence and earlier adaptive selection are unresolved.
- 2026-01..2026-10 data was deliberately **NOT** accessed by Week 3 workflow.
- No prospective sealed independent holdout; no live execution, merge, or deployment.

## Acceptance
A successful GitHub Actions job establishes engineering execution only. All 21 combinations must be reported including negative results. Even a positive simulated return cannot establish statistical profitability or authorise promotion.
