# Local paper-trading acceptance evidence — 2026-11-13

Branch: `research/local-paper-acceptance-20261113`; stacked draft PR #111 on #108. **NOT RELEASED.**

## Independent user-device evidence (Android Termux)
The operator provided screenshots of a BTC-USD simulated buy and sell. Read-only SQLite accounting reconstructed two fills, a zero BTC position, cash USD 9999.230353857565, and net P&L including fees USD -0.769646142435. An initial recovery check pointed to a different SQLite path and therefore falsely reported starting cash USD 10000. Corrected recovery against `~/.alpha-labs-paper/alpha-paper.sqlite3` reported recovery verified, startup halted, cash USD 9999.230353857565, BTC position zero and two events. These are **operator screenshots**, not an independently reproduced device test. The original journal and backup must remain untouched.

## Engineering changes in this PR
- Add `tests/unit/test_local_paper_acceptance_20261113.py` using isolated temporary SQLite files and mock CLI sessions.
- Assert risk thresholds (0.25% single position, 1% aggregate, 2% daily, 5% drawdown, 1x gross), rejection paths and simulation-only decisions.
- Assert restart recovery is HALTed, restores cash and positions, and requires rearming.
- Assert an injected invalid journal digest fails closed.
- Assert the CLI rejects disabled stock/ETF markets, shell commands and malformed orders.
- Include new tests in the existing free-local-paper GitHub Actions workflow.

## Ten-task acceptance register
| Task | Status | Outstanding acceptance |
|---|---|---|
| 1. Regression | TESTS ADDED | CI execution and independent test review |
| 2. Journal tampering | TEST ADDED | protected checkpoint, missing/reordered/truncated journal scenarios |
| 3. Risk thresholds | TESTS ADDED | integrated portfolio boundary tests |
| 4. Quote resilience | EXISTING ADAPTER | adversarial network disconnect/recovery, stale/future replay |
| 5. Protective stops | EXISTING IMPLEMENTATION | deterministic gap, slippage, depth, partial-stop tests |
| 6. ETH/SOL | EXISTING THREE-COIN FEED | separate full trade/restart tests |
| 7. Stock/ETF | CATALOGUE ONLY | licensed data, calendars, corporate actions, FX; no paper orders |
| 8. Analytics | EXISTING STATE | verified P&L and NAV reporting on multi-asset replay |
| 9. Android dashboard | TERMINAL ONLY | graphical mobile interface and device acceptance |
| 10. Release evidence | DRAFT PR | all tests passing, review, backup/checkpoint, Android acceptance |

## Security and operations
No real orders, API credentials, network listener, paid infrastructure, merge or deployment. The added tests must never use the operator's real Android database. GitHub CI and independent Android acceptance remain unverified until executed and inspected.
