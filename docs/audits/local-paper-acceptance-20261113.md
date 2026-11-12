# Local paper acceptance · 13 November 2026

**CONDITIONAL GO for limited local simulated research on a disposable or verified working journal.** Physical Android and the two original device files remain pending acceptance. Private staging and real-money operation are NO-GO.

## Reproducibility

- Baseline main commit b9098035638d45fddd7dcbab9a784d034ad80def. Tested candidate application tree e7103702ec2de3dd1df35a3f49a537566a44ba23. The acceptance documentation commit adds evidence. The draft PR links exact remote commit and CI receipts.
- Managed Linux CPython 3.12.14 and 3.13.5, pytest 9.2.0, Python 3.13 SQLite 3.46.1, Node 24.22.1, Ruff 0.15.22, Bandit 1.9.4 and resolved cryptography 50.0.2.
- Separate hosted-source tests used cfef52790c6905182e97ba4df1a72fef82e0b6b8 with disposable PostgreSQL 16.2. PostgreSQL is outside the local terminal dependency path.

~~~sh
PYTHONPATH=packages/alpha_lab/src:.:tests/integration python -m pytest tests/unit tests/integration -q --junitxml=local-paper.xml
PYTHONPATH=packages/alpha_lab/src:.:tests/integration python -m pytest tests/unit/test_local_*.py tests/unit/test_coinbase_future_clock_tolerance.py tests/unit/test_live_paper_service.py tests/unit/test_paper_commit_boundaries.py tests/unit/test_paper_control_checkpoint.py tests/unit/test_paper_runtime.py tests/unit/test_public_https_security.py -q
make verify
ruff check packages deployment tests scripts/engineering_status.py scripts/local_paper_live_smoke.py
bandit -q -r packages deployment -ll -f json -o bandit.json
pip-audit --strict -r runtime-requirements.txt --format json
PYTHONPATH=packages/alpha_lab/src python scripts/local_paper_live_smoke.py
~~~

Generate runtime-requirements.txt from pyproject.toml project.dependencies. The smoke command is opt-in and executes only against a new temporary SQLite journal. The deterministic CI suite uses fixtures and controlled clocks.

## Acceptance matrix

| Area | Result | Evidence |
|---|---|---|
| Full Python suite | PASS | 330 tests and 97 subtests on CPython 3.12.14, and the same on 3.13.5. |
| Local Python 3.13 selection | PASS | 75 tests and 49 subtests. |
| Existing project commands | PASS | make verify ran 317 unittest cases and 36 website tests. The named synthetic research fixture also ran successfully. |
| Structural, chain and accounting checks | PASS on disposable data | Fresh and normal restart, open/closed positions, duplicate or missing events, sequence/hash/payload tamper, invalid checkpoint, rollback, corruption and alias rejection. |
| Legacy schema compatibility | PASS on disposable data | Exact #108 checkout ab21e1f generated a two-fill BTC journal and separate backup. Migration of its verified copy recovered USD 9999.789989984995 and HALT. SHA-256 of both source files matched before and after. |
| Recovery and crash handling | PASS on disposable data | Process termination before/after commit, same-ID retry, multi-asset replay, active-writer and sidecar denial, independent backup receipt restore and repeated restart. |
| Deterministic risk | PASS on fixtures | Startup HALT, stale/outage HALT, last-check outage, no auto-rearm, manual halt, limits, buy stop, partial fill and gap/slippage paths. |
| Quote integrity | PASS on fixtures | Out-of-order and same-sequence conflicting depth, restart watermark, bounded timestamp lead, 429 recovery, redirect, size/framing, non-finite and crossed books. |
| Public Coinbase connectivity | PASS with transient failure recorded | A SOL timeout stopped the first final-source execution attempt before order submission. A new request passed all three books without changing the 10-second freshness limit. |
| Live-quote simulated execution | PASS on disposable Linux | A BTC, ETH and SOL buy and sell each produced six simulated fills total. Restart recovered USD 9999.96866379775272355, zero open positions and startup HALT. |
| Android original and backup | NOT TESTED | Neither file was accessible in the Linux executor. Historical device evidence is retained below. Execute the [read-only Termux runbook](../operations/android-paper-recovery.md). |
| Hosted Auth0, TLS and custody | BLOCKED | Public issuer metadata and health-only probe were observable. Hosted app login, owner/tenant and independent trust custody remain open. |
| Static and dependency security | PASS in scoped checks | Ruff, Bandit medium/high and strict runtime dependency audit. Draft PR carries the exact-head Actions receipts. |

### Live sample and timing

The passing final-source sample recorded BTC, ETH and SOL at exchange sequence 139225549773, 104970365973 and 33746624467. Exchange-to-receipt ages were 2.233381 s, 0.828865 s and 1.039550 s, respectively. The receipt timestamps are around 01:48:48 AEST on 13 November. Request duration was approximately four seconds for the three parallel calls. The observed timeout and different request/quote ages are separately recorded. The earlier Android clock lead was not reproduced on Linux. These results support keeping the existing bounded clock-lead tolerance and improving diagnostics rather than increasing freshness.

## Instrument matrix

| Instrument group | Catalogue | Historical scope | Live quotes | Local execution and acceptance |
|---|---|---|---|---|
| BTC-USD, ETH-USD, SOL-USD | Supported Coinbase profile | Research OHLCV adapters exist. Matching Coinbase history was outside this run. | Verified public top-of-book source, timestamp and sequence | Simulated BUY and SELL and restart passed on Linux. Candidate sizes use fixed research precision of 0.00000001 asset units. The product metadata endpoint returned HTTP 403, so current venue lot-size metadata was not confirmed. |
| SPY, QQQ, IWM, XLF, XLE | Listed | Explicit synthetic fixture only in this candidate | Gated on verified entitlement and provider | Rehearsal only. All five executed in the synthetic USD profile with whole shares and explicit UTC session windows. |
| Other crypto, US and ASX catalogue entries | Discovery | Provider-specific inputs require separate review | Disabled for this profile | Research-only. Venue precision, licensing, corporate actions, holidays and FX require validation. |

The account uses virtual USD. Market orders consume available displayed depth. Limit orders may remain pending or fill partly. Protective stop execution is modeled against the current bid and available depth, including simulated slippage. No profitable strategy or execution at a real venue is inferred from the smoke.

## Historical #111 record

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
