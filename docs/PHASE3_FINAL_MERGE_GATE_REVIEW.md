# Phase 3 final independent review — merge gate

**Decision: BLOCKED — do not merge PR #75.**

## Evidence
- The isolated PostgreSQL Actions job (run 42634526259) completed successfully. Its two tests demonstrate one-winner duplicate insertion and uniqueness across separate database connections using a disposable PostgreSQL 16 service.
- Existing research and Sites workflows passed at commit 22d64c236107c86fb7d12ebe7718041b2a9ea589.
- Current NYSE static calendar fixtures are not a live authoritative calendar integration.

## Critical gap 1: Exchange-session enforcement
`backtest/engine.py:replay` calls `require_final_candle` based on minimum observed bar spacing. It does NOT call `require_settlement_at_open` or require exchange session metadata. Consequently, valid candle timestamps alone cannot exclude a holiday/closed-session bar. Further, `next_eligible_open` chooses a subsequent session opening even when an intraday next bar is valid; it cannot be applied unmodified to every next-bar strategy.

**Required:** a venue-specific, explicit, source-versioned schedule with timezone/DST and exceptional closure handling; enforce it at each order's execution timestamp; distinguish next eligible intraday bar from next session open. Fail closed when the calendar is unavailable. Crypto 24/7 is a separate policy.

## Critical gap 2: Independent financial reconstruction
`reconcile_long_only_orders` sums the order-provided outlay/proceeds and fees, then compares against the replay NAV. It does not independently calculate the expected price, fee, slippage or outlay from raw candle and cost assumptions. Both producer and verifier can agree on a wrong order ledger. No validation that order fee equals the cost-model fee or that each order timestamp and price match source candles.

**Required:** independent reconstruction from immutable source OHLCV, cost model, order intent and timestamp; verify every order's quantity, execution price, fee, cash, realised/unrealised P&L and NAV, including open positions and negative cases. Retain exact Decimal arithmetic.

## Additional review notes
- `CostModel.__post_init__` checks finite values but retains input types without coercion; non-Decimal input may behave unexpectedly in arithmetic.
- The PostgreSQL run registry adapter is not wired to every research-run creation path; uniqueness in a disposable test schema is not proof of system-wide enforcement.
- CI success proves the current tests passed, not that the missing entry-point invariants are enforced.

## Required acceptance
1. Add fail-closed calendar-aware execution validation and tests that inject a plausible OHLCV candle during a closed session.
2. Independently reconstruct all ledger economics from source data; include tampered fee, execution price, slippage, partial/open position and holiday scenarios.
3. Verify registration is invoked transactionally on every run-creation entry point.
4. Re-run all Python and PostgreSQL workflows on the resulting head SHA and obtain independent code review.

No merge, deployment, credential changes or trading activation.
