# Alpha Labs authentication research consolidation — 2026-11-10

## Decision
**NO-GO for merge to main, deployment, paper execution, or live trading.** Preserve the existing public GPT Site. This document is an inventory and review gate, not production approval.

## Current integration lineage
PR #84 is a **stacked research PR**, based on #83's branch, which itself is based on #82, #79, #78, #77, #76 and their earlier staging/authentication dependencies. PR #84 is **not** a standalone patch against main. The comparison to main currently includes 151 commits and 130 changed files; this is too broad for an unreviewed merge.

## CI and historical failures
- PR #84 at commit adffaec759ff46129f249671998027485b226679: five of five pull-request checks PASS.
- PR #76 at 529c21b: historical offline suite failure: missing `cryptography` dependency in test runner. PR #77 was explicitly created to fix this and its own checks PASS. Do not interpret the old PR #76 check as a fresh failure on #84.
- PR #42 at 7130307: historical offline suite failure: three assertions expect a 'non-finite numeric input' message but the fail-closed implementation returns 'HALT'. Do not loosen HALT enforcement merely to green an old branch; reconcile the assertions and intended error contract before changing code.
- Other inspected open PR heads did not report failed checks; the presence of a green historical run is not proof of deployability or compatibility with main.

## Consolidation strategy
1. **Retain** PR #84 as the single integration review tip. Keep earlier stacked PRs as auditable ancestry until each unique change has been reconciled.
2. **Do not merge** the entire stacked chain into main. First produce a minimal, reviewed integration diff from a current-main branch, separating authentication, database roles, deployment entry and CI.
3. Verify that Auth0 OIDC browser flow, PKCE, callback origin, state/nonce, issuer/audience/JWKS, session revocation, tenant roles, RLS, proxy peer and fail-closed readiness each have explicit adversarial acceptance evidence.
4. Run isolated PostgreSQL 16 and full offline tests on the exact candidate head. Prohibit production/staging database DSNs in CI.
5. Obtain real Auth0 browser, actual Render proxy peer and independent security review before staging deployment approval.
6. Close a stacked PR only after its changes are demonstrably included in the reviewed successor, no unique work is lost, and GitHub records the replacement. Do not delete research branches merely to reduce notifications.

## Notification control
Research branches should normally use pull-request checks; pushes to main may still run full CI. Keep required security checks and failure notifications available. Email delivery preferences are a separate user-account setting.

## Hard restrictions
No merge, deploy, live or paper trading activation, credential rotation, database modification, GPT Site modification or assumption of verified profitability without explicit, evidence-backed acceptance.
