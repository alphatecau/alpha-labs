# Personal Edition paper-engine acceptance checkpoint — 2026-11-11

Research branch: research/personal-edition-paper-verification-20261111
PR: #89 (draft)
Verified latest test head: 126580b093885d45f79d7a4bb82b6be0eaf6d7a7

## CI evidence
- Research workflow: https://github.com/alphatecau/alpha-labs/actions/runs/42940546670 — success.
- Research job log: 236 tests passed; explicitly includes test_append_failure_cannot_change_authoritative_ledger, test_duplicate_rejected_in_process_and_after_restart, and test_invalid_order_id_halts.
- Existing Sites workflow: https://github.com/alphatecau/alpha-labs/actions/runs/42940546672 — success.
- No human review submission was returned for PR #89 at checkpoint time.

## What passed
- Offline simulated ledger cash/NAV fee oracle, risk limits and restart recovery.
- Journal hash-link and payload tampering, missing middle event.
- Optional order ID duplication within a runtime and after restart.
- Mocked append failure leaves ledger unmodified and forces HALT.

## Not yet accepted for production paper service
1. Order ID is optional for legacy callers; mandatory request IDs and client retry semantics are not yet enforced.
2. Duplicate-order protection has not been verified across multiple processes/concurrent runtime instances.
3. Journal chain cannot independently detect rewriting of all events or deletion of the final event without a separately trusted checkpoint.
4. No independent realised/unrealised P&L and tax-lot accounting acceptance.
5. No external authenticated BFF integration, trusted ingress acceptance, live Auth0 browser test, database isolation test or independent security sign-off.
6. Passing offline CI is not evidence of strategy profitability or safe live execution.

## Merge/deployment recommendation
Retain PR #89 as draft pending review of persistence and concurrency semantics. Do not deploy or enable broker execution. Merge only after review and a clear decision on optional IDs, concurrency, checkpoint anchoring and accounting acceptance. This file is a research checkpoint, not a security approval.
