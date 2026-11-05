# Multi-year evidence acceptance review — 5 November 2026

**Decision:** engineering evidence passes for research infrastructure integration. **Reject EMA(12,48) for forward-trading promotion.** Trading remains disabled.

## Evidence identity and method

- Input: `AlphaLabs_Evidence.zip`, wrapping `AlphaLabs_Research_Evidence_COMPLETE_20261105.tar.gz`.
- Inner archive SHA-256: `bb949f86418f007c766a882e15e25c38ad517d8343b18c380d1d464f79316ce9`, matching the phone's export output.
- All 324 inventoried members passed byte-count and SHA-256 checks; the additional bundle manifest makes 325 files in total.
- All 110 captured Python source files match GitHub blobs at `6c95ddebbba1ea858372261da8ac87575133a8b8`. Replay used the separately reviewed local source rather than executing unverified attachment code.
- Independently parsed 99 selected monthly source ZIPs and checksum pairs. Each BTC/ETH/SOL dataset contains 24,144 consecutive hourly candles across April 2023–December 2025: 72,432 observations overall, with no missing hours, early-close anomalies or zero-volume candles in the selected window.
- Reconstructed canonical OHLCV CSVs from raw ZIPs and compared their complete bytes with the supplied CSVs. Frozen-spec and dataset/manifest hashes also verified.
- All three complete JSON reports reproduced using the reviewed Python engine. A separate audit EMA recurrence and ledger agreed on final liquidatable NAV, modelled fees and order counts for all three partitions, passive benchmarks and doubled-cost cases: 27 comparisons.
- Nine current same-provider REST samples (three per market, spanning April 2023, the January 2025 timestamp transition and December 2025) matched source OHLCV. This is sampled corroboration from the same provider, **not independent venue price authentication**.

Machine-readable findings and full-precision metrics: [`evidence/2026-11-05_REPRODUCTION_AUDIT.json`](evidence/2026-11-05_REPRODUCTION_AUDIT.json).

## Source anomaly correction

| Cached BTC archive | Findings | Outcome |
| --- | --- | --- |
| January 2023 | 744 hourly candles; row 565 has canonical close metadata; no anomaly | Complete source month |
| March 2023 | 743 candles; row 565 opens 24 March 12:00 UTC with early close `1679661581646`; missing 13:00 UTC candle | Reject as an uninterrupted monthly dataset |

The March row's canonical close would be `1679662799999`; it is 1,218.353 seconds early and has zero reported volume. The next row opens at 14:00 UTC. The parser correctly preserves this source evidence and rejects the missing hour. The original January attribution was inaccurate; this review corrects it from the cached bytes. The selected April–December research window excludes the rejected month without interpolation.

## Frozen baseline results

Final **unsealed** test window: 15 June 2025 19:00 UTC through 1 January 2026 00:00 UTC, exclusive; 4,781 hourly observations per market.

| Market | Strategy return | Passive return | Excess vs passive | Strategy at 2× friction | Strategy max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT | −11.012% | −3.448% | −7.564 pp | −16.158% | 12.546% |
| ETH/USDT | −0.709% | +3.226% | −3.936 pp | −5.497% | 10.003% |
| SOL/USDT | −7.346% | −3.739% | −3.607 pp | −12.027% | 13.655% |

These are modelled returns after the frozen execution-friction assumptions, denominated in USDT. Each partition starts independently at 10,000 USDT with a 20% initial-capital allocation budget. Passive hold uses the same starting allocation, not dynamically matched risk or exposure. Fees and adverse slippage are each 10 bps per side; operating expense is explicitly assumed to be zero. A final open position is valued with hypothetical exit costs. These are not actual fills, AUD returns or a continuous compounded multi-year portfolio return.

All three strategy test returns are negative and below passive hold. The strategy also underperforms its passive comparator in every training and validation partition. This is sufficient to reject promotion of this baseline under the frozen assumptions; it does not establish that another strategy will be profitable.

## Gate decisions

| Gate | Decision |
| --- | --- |
| Bundle integrity and source-code identity | Passed |
| Selected source chronology and source-to-CSV linkage | Passed |
| Cached January/March anomaly inspection | Completed; March rejected |
| Full report and separate ledger reproduction | Passed |
| Independent venue price authentication or historical publication-time reconstruction | Not established |
| Untouched holdout, statistical significance and multiple-testing adjustment | Not established |
| EMA economic promotion screen | Failed |
| Paper/live execution or capital release | Not approved; disabled |

The window was selected after data-quality inspection, and its results are already observed. Preserve the original evidence and comparator; do not tune EMA parameters and reuse these results as an untouched final test.

## Next development gate

Proceed with research infrastructure integration after current CI passes. Strategy Research v0.8 begins with a registered regime-filtered momentum hypothesis, a bounded candidate/parameter budget, explicit falsification criteria, realistic cost and operating-expense assumptions, and a prospectively collected evaluation set. Then consider volatility-targeted trend following and mean reversion in the agreed order. AI, broker access and autonomous execution remain outside this release.
