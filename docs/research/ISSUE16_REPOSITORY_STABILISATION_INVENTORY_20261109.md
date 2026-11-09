# Issue #16 repository stabilisation inventory — 2026-11-09

Research-only / NO-GO. GitHub metadata inventory, not a complete code audit. No PR may be merged or closed on this evidence alone.

## Pinned state
- Main: a3b6c9917a5644d7b13e84c88966fc8491f4b9d9
- PR #43 verified head: 8d7ae36d18b79d3ee26fbe97374f1a45482fee8b
- Success: Issue #16 verification run 42543153346; offline research run 42543153329; Sites run 42543153341.
- Earlier run on 6aa92ad8: 206 tests, 3 skipped (cryptography absent). Fixed dependency on 8d7ae36. Archive exact test counts and skip evidence before certifying gate.

## Open PRs and provisional disposition
| PR | Subject | Action |
|---|---|---|
| 43 | Main-based Issue 16 CI | Keep draft, archive no-skips evidence |
| 42 | Paper runtime risk authority | Keep draft, audit bypass paths |
| 37 | Older Phase 1 adversarial verification | Keep draft, compare test overlap with main |
| 36 | Issue 16 review | Keep draft, retain audit findings |
| 35 | Phase 2 crypto CI | Keep draft, compare overlap with #43 |
| 34 | Phase 2 integration | Keep draft, verify dependency chain |
| 33 | Consolidated assurance review | Keep draft, documentary input |
| 32 | Independent NAV/cost oracles | Priority review and differential testing |
| 31 | Archive provenance tests | Priority review and external-source validation |
| 30 | HTTP mutation boundaries | Priority security review |
| 29 | Phase 2 entry-point inventory | Compare against #28/#30 and main |
| 28 | Phase 2 enforcement | Compare against #29 and main |
| 27 | Post-merge audit | Determine whether #33 supersedes |
| 17 | Phase 1 audit (not marked draft) | Do not merge; review safety state |
| 14 | Behavioural prototype | Defer |
| 12 | Global foundation | Defer |
| 11 | Legacy research gates | Compare with main |
| 10 | Rejected strategy v0.9 | Preserve negative evidence |
| 9 | Rejected strategy v0.8 | Preserve negative evidence |

GitHub returned 19 open PRs. No merges, closures or production changes authorised.

## Mandatory next gates
1. Compare actual diffs and modules against main, preserve the authoritative baseline and fail closed on duplicate promotion paths.
2. Verify full CI including minimum test counts, zero skips and deliberate failure detection.
3. Differential Decimal accounting oracle: NAV, cash, partial fills, fees, realised/unrealised P&L and liquidation costs; randomised invariant tests.
4. Signed archive provenance plus independent source reconciliation, causal timestamps and sealed holdout integrity.
5. Independent runtime security, risk-authority HALT persistence and HTTP mutation boundary checks.

CI success alone does not establish market-data truth, profitable strategy performance or production readiness. Live trading, broker integration and deployment remain disabled.
