# Alpha Labs — Week 2 frozen historical audit (2026-11-08)

## Immutable source
Original research run: https://github.com/alphatecau/alpha-labs/actions/runs/42471018274
Original artifact ID: `13613248485`
ZIP SHA-256: `5f6007bd36125e047879b8cc7c4d162938a53b2ce120b95199cee92b0b165986`
The audit script rejects any ZIP with a different digest. The source contains nine JSON reports plus a summary, for BTCUSDT, ETHUSDT and SOLUSDT, with 10/10, 20/20 and 40/40 bps fee/slippage per side.

## Historical findings (single continuous replay; not walk-forward validation)
| Market | 1x costs | 2x costs | 4x costs | Positive out of 5 chronological NAV slices at 1x / 2x / 4x |
|---|---:|---:|---:|---|
| BTC | +2.91% | +0.16% | -3.96% | 5 / 2 / 0 |
| ETH | +1.73% | -0.01% | -2.80% | 3 / 3 / 1 |
| SOL | +4.91% | +3.33% | +0.64% | 3 / 2 / 2 |

SOL 1x chronological NAV slices: +3.43%, +1.44%, +0.07%, -0.07%, -0.01%.
SOL 2x slices: +3.01%, +1.09%, -0.25%, -0.25%, -0.28%.
SOL 4x slices: +2.31%, +0.48%, -0.80%, -0.56%, -0.75%.
The latter slices are generally weak. Positive aggregate return is not evidence of stability or positive future expectancy.

## Statistics and limitations
The audit script calculates circular 14-day moving-block bootstrap intervals from 24h NAV log returns. It uses a 95% Bonferroni correction across the **three assets** for each cost tier. This does not correct for adaptive strategy selection, different cost tiers, repeated earlier experiments, or uncertainty in execution modelling. It is a descriptive sensitivity calculation, not an inferential green light. The existing NAV reflects one uninterrupted backtest; slicing NAV does **not** restart positions or independently retrain models and is **not** a fresh walk-forward experiment.

The frozen JSON artifact does not contain underlying hourly market OHLC. Consequently market regime analysis (uptrend, downtrend, sideways, volatility expansion) cannot be completed from this artifact alone. Re-download verified historical archives, rerun frozen model in genuinely chronological embargoed partitions and assess regimes using only past bars. Do not call retrospective fold slicing independently validated.

## Gates
- **PASS:** Original GitHub run's unit tests, checksum-verified archive acquisition, three-market cost stress, accounting reconciliation and artifact upload.
- **IMPLEMENTED, AWAITING CI:** Frozen-artifact digest gate, chronological NAV concentration analysis, descriptive block-bootstrap uncertainty and automated research-only audit.
- **BLOCKED:** Fresh fold-wise walk-forward replays, genuine market-regime attribution, independently sealed holdout, independently verified executable fills, portfolio-wide risk authorisation.
- **Decision:** INCONCLUSIVE; no strategy promotion, no live trading, no merge, no deployment.

## Reproduction
Download original artifact ZIP from run 42471018274, verify SHA-256 above, then:

```sh
python scripts/week2_frozen_artifact_audit.py original.zip --output week2-output/frozen-audit.json
```

The new workflow `.github/workflows/week2-frozen-audit.yml` performs this automatically using GitHub's read-only Actions token.
