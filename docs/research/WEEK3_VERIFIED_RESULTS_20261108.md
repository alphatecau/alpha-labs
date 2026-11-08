# Week 3 development diagnostics — verified execution and decision (2026-11-08)

**GitHub Actions:** https://github.com/alphatecau/alpha-labs/actions/runs/42472475226 — success, head commit `f5e95d7a0d7f1b68e1f2afa26b7e14850892b060`. All unit-test, archive-verification, simulation, safety and artifact-upload steps succeeded.

**Artifact:** `alpha-labs-week3-development-diagnostics`, ID `13614440771`, SHA-256 `860bf30a49608edb36e68bdc20e998817f94f3b73579da2f3b48f249db63d465`. Contains `development.json`, 21 scenarios × 5 chronological folds = 105 modelled evaluations. Each fold reports cash-ledger reconciliation PASS. Research and promotion flags are false.

## Mean modelled fold return (%)
| Hypothesis | Market | 10 bps each side | 20 bps each side | 40 bps each side |
|---|---|---:|---:|---:|
| H1 trend | BTC | -2.5961 | -4.7836 | -4.9825 |
| H1 trend | ETH | -2.5710 | -4.5872 | -5.0571 |
| H1 trend | SOL | +0.2307 | -2.3481 | -4.8664 |
| H2 mean reversion | BTC | -4.2714 | -4.9063 | -4.9564 |
| H2 mean reversion | ETH | -3.0205 | -3.9808 | -5.0358 |
| H2 mean reversion | SOL | -1.9979 | -2.9677 | -4.2868 |
| H3 rotation | BTC/ETH/SOL portfolio | +0.4888 | -1.7276 | -3.1540 |

H3 at baseline costs had 3/5 positive folds, 293 closed trades summed across folds. H1 SOL at baseline had 3/5 positive folds and 537 closed trades. **Every candidate is negative at 20 and 40 bps fee/slippage each side**. Every 21-comparison Bonferroni p-value is 1.0. These are retrospective development diagnostics, not independent holdout results.

## Decision
**FAIL for strategy promotion; PASS for research pipeline execution.** No demonstrated cost-robust edge. Do not select H3 based on this result or retune the same previously examined history without recording exploratory status.

## Limitations and next engineering gates
- H1/H2 use one-asset targets and H3 portfolio rotation; all share 20% allocation ceiling. No risk-matched passive benchmark or regime-specific realised P&L has been implemented.
- Independent portfolio risk authorisation is not implemented. Cash-delta reconstruction is not independent position/NAV accounting.
- Historical periods have been examined before; sign tests over five potentially dependent folds do not establish independent statistical inference, even with 21-way Bonferroni correction.
- Hourly OHLC modelled stop fills are not independently executable prices. A prospective sealed holdout and execution evidence are required before promotion.
- The run used `f5e95d7`; subsequent documentation-only commits were not part of this CI snapshot.

**Safety:** no live trading, merges or deployment; draft PR #15 unchanged.
