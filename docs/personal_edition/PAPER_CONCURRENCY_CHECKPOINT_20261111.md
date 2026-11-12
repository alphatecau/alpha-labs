# Paper-engine concurrent journal verification — 2026-11-11

Research-only PR #89. No broker integration, deployment, or live trading.

## Changes
- Corrected the stale-writer test: optimistic journal-head mismatch takes precedence over duplicate ID detection.
- Added a two-thread/two-connection SQLite contention regression. Exactly one stale-snapshot append should commit; the other must fail closed.
- Added a tail-deletion demonstration: local chain verification alone cannot identify removal of the final event; comparison against a previously trusted head reveals the change.

## Limits
- Thread contention is not a substitute for independently scheduled operating-system processes or crash/recovery stress.
- The checkpoint demonstration does not implement durable, independently trusted checkpoint storage.
- Per-append duplicate ID detection currently scans journal payloads; performance and explicit indexed uniqueness remain to be addressed.
- No external authenticated dashboard or live execution has been accepted.

## Required gates before merge
Latest-head CI success, real multi-process stress test, trusted checkpoint design, independent P&L reconciliation and review.
