# Day 2 accounting security and independent evidence audit — 2026-11-09

Status: **RESEARCH ONLY / MERGE HOLD** until all required CI checks pass on final integration SHA.

## Scope and source
Draft PR #54, branch `research/day2-independent-accounting-oracles-20261109`. The accounting module reconstructs cash and positions from fill records and computes liquidation NAV. The new P&L reporter independently tracks weighted-average cost basis, gross and net realised/unrealised P&L and fee allocations. Both use Decimal arithmetic. Tests are synthetic; no independent market prices, authenticated broker fills, external statements or sealed holdout were supplied.

## Independently calculated fixture
Starting cash 1000; BUY 2 BTC at 100 with fee 1; SELL 0.5 BTC at 120 with fee 0.3; final mark 110; liquidation haircut 25 bps.

- Cash: 1000 - 201 + 59.7 = **858.7**
- Remaining inventory: **1.5 BTC**; gross remaining cost basis 150; unallocated entry fee 0.75.
- Realised gross P&L: 0.5 × (120 - 100) = **10**.
- Realised net P&L: 10 - 0.25 allocated buy fee - 0.3 sell fee = **9.45**.
- Unrealised gross P&L: 1.5 × 110 - 150 = **15**.
- Unrealised net P&L: 15 - 0.75 = **14.25**.
- Mark NAV before liquidation: 858.7 + 165 = **1023.7**.
- Liquidation haircut: 165 × 0.0025 = **0.4125**.
- Final liquidation NAV: **1023.2875**.
- Net P&L after liquidation: 9.45 + 14.25 - 0.4125 = **23.2875**.
- Identity: 1000 + 23.2875 = **1023.2875**.

Independent assertions are recorded in `tests/unit/test_day2_pnl_reporting.py`, `test_day2_pnl_identity.py`, and `test_day2_pnl_adversarial.py`; multi-asset fixtures also check fee allocation and NAV.

## Security and accounting gates
- Fail-closed: negative cash, naked sale, invalid side/quantity/fee, nonfinite numbers, duplicate supplied fill IDs, unsupported fee currency, and mismatched cash deltas are rejected.
- Single quote currency only; no currency conversion or FX accounting.
- Long-only; no shorting, borrowing, funding, derivatives, corporate actions or margin.
- Weighted-average cost basis is explicitly declared, not FIFO or tax-lot accounting.
- No independent source authentication, signed fill provenance, bid/ask observation or timestamp integrity for these P&L reports. A missing fill_id is currently accepted; uniqueness is only enforced when supplied.
- The source ledger allows cash-delta absolute tolerance of 1e-12 and comparison of reported balances at 1e-8; production-grade precision/rounding policy remains undefined.
- P&L report uses Decimal context default precision; pathological repeating partial fills and extreme magnitude/scale have not been independently proven.
- Execution shortfall against reference midpoint is not a verified decomposition of spread, impact and slippage. Do not report those as independently measured.
- Current accounting tests do not establish real market profitability, broker reconciliation or promotion eligibility.

## CI evidence
Prior integration SHA `06c001c29118c5ce47c30099f3e2b7d5a1202a94`: research run https://github.com/alphatecau/alpha-labs/actions/runs/42571626043 passed 228 tests with three cryptography-related skips; website run https://github.com/alphatecau/alpha-labs/actions/runs/42571626050 passed. Dedicated cryptography-enabled full-suite workflow added to this branch to require zero skips. **Do not treat the prior CI as verification of the new workflow or this final branch head.**

## Release decision
**NO-GO for merge, dashboard integration, deployment and trading.** Await final-head research, website and zero-skip cryptography CI, then address fill provenance, numerical precision policy and independently authenticated market data before any production-readiness claim.
