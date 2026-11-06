# Strategy Research v0.9 follow-up review

**FAIL for promotion.** The six registered variants and the two additional exploratory rules failed their respective screens. All market results use previously examined data. The exploratory rules used only development and validation partitions, leaving the former final partition outside their scoring. See the [fixed protocol](30_STRATEGY_V09_FOLLOWUP_PROTOCOL.md).

| Work | Outcome |
| --- | --- |
| Pinned v0.8 and v0.9 reproduction | PASS |
| Corrected same-open risk replay and independent parity | PASS |
| Fixed 20/40/60/80 bps grid and repeatability | PASS |
| Registered breakout and mean-reversion variants | FAIL |
| Exploratory trend and relative-strength rotation | FAIL |
| Directional downtrend diagnostic | INCONCLUSIVE |
| Spot SHORT, broker rejects and partial fills in OHLCV replay | UNSUPPORTED |
| Admissible execution data, realised costs and prospective evaluation | UNVERIFIED |

## Root cause and correction

The [v0.8 attribution](27_STRATEGY_V08_LOSS_ATTRIBUTION.md) identifies a negative gross signal in BTC and SOL and execution friction larger than gross ETH P&L. Short holds and rapid re-entry increased turnover. The v0.9 breakout had positive after-cost performance in its final unsealed period, but its weak forward-fold consistency and sparse sample defeated promotion. The new cost grid does not change the original screening rules.

The shared-cash replay now checks equity after every simulated entry at the opening mark. If a fill consumes the remaining daily-loss or drawdown allowance, later entries at that open are rejected. A suspension persists through a price recovery and flattens any remaining positions at the next modelled executable open. The regression test covers three simultaneous market proposals and a same-hour recovery. The independent float ledger implements the same timing separately. Standalone research risk tests also exercise stale quotes, invalid data, unsupported sides and the kill switch. Exchange responses and operational HALT remain outside this replay.

## Reproduction

Use Python 3.12 or later and the audited `raw/` and `curated/` trees described in the [multi-year review](25_MULTYEAR_EVIDENCE_REVIEW_20261105.md). Run from the repository root and choose unused output paths.

```sh
export PYTHONPATH=packages/alpha_lab/src
python scripts/strategy_v08.py --data-root /path/to/verified-data --output-dir /tmp/v08
python scripts/audit_strategy_v08.py --data-root /path/to/verified-data --reports /tmp/v08
python scripts/strategy_v09.py --data-root /path/to/verified-data --output-dir /tmp/v09-corrected --verify
python scripts/strategy_v09_followup.py --data-root /path/to/verified-data --output /tmp/v09-followup.json
make verify
```

Use source commit [`c5d9e7e`](https://github.com/alphatecau/alpha-labs/commit/c5d9e7e76042b91b230af074b89e74dcaa0a7d77) to regenerate the original v0.9 reports and their original implementation hashes. The corrected run has its own implementation hashes. Source data, vendor order books and the detailed replay output remain separate from this public review.

## v0.10 priority

Establish a permissible, point-in-time spot data set with quote, trade, depth and event/arrival timestamps. Use the resulting size and latency distributions to stress an entry and exit at a predeclared size, including spread widening and book depletion. If the data and costs clear review, freeze a single new hypothesis, an event-count and power target, cost and risk thresholds, data custody and a one-time evaluation protocol. Preserve the reserved 1 January 2027 to 1 January 2028 UTC period. Live execution stays disabled.
