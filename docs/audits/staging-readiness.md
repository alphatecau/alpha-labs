# Staging readiness — research-only acceptance decision

## Decisions

| Target | Decision | Status / basis |
|---|---|---|
| Offline research | GO for tested research paths | VERIFIED: synthetic smoke, existing website/research regression, unit, risk, accounting and security suites pass |
| Private owner paper staging | NO-GO for staging acceptance | BLOCKED: real Auth0/TLS proxy, storage permissions, protected checkpoint/restore, hosted identity integration and device/browser evidence remain outstanding |
| Public paper deployment | NO-GO | BLOCKED: no public/multi-tenant acceptance, one-writer/one-owner design, no deployment authorized |
| Real-money trading | NO-GO | NOT_APPLICABLE: expressly prohibited; paper path has no broker execution adapter |

Passing CI is not staging acceptance or permission to deploy. No merge into main, branch deletion, deployment, credential modification, production database operation or live order occurred.

## Review and dependency order

1. Draft #103, `0c0a99f62f8e25df6c66a74ea8447922f57ea16d`: main-based CI/Ruff/dependency repairs. Replaces the repair intent of #97/#100; recommend their closure only after owner review of the replacement. No PR was closed automatically.
2. Draft #104, `f41e8c7ee43575d50771ddc4cfe96389c468243e`, based on #103: existing #93 → #95 → #96 and #92 → #94 stacks reconciled against stronger main security controls. Review ownership/revocation, tenant role boundary and shared quota separately even though the integrated draft retains their ancestry.
3. Owner-paper integration draft on `research/master-integration-20261112`, based on #104 and retaining #101 ancestry: database order uniqueness, recovery/lock reconciliation, owner OIDC boundary, private local dashboard and acceptance/audit reports. Review simulated accounting/commit boundaries before enabling any API listener.
4. #99 is SUPERSEDED: its four original unittest cases run successfully against main's merged #98 implementation and the assertions already exist there. It is assertion-equivalent, not byte-identical. Recommend closure after review; leave the branch and PR intact.
5. #92 alone is SUPERSEDED by #94's reproduced stale-head/incomplete-evidence repairs. Historical #42/#76 still have failed exact-head CI; retain the evidence rather than presenting the rollup's green checks as repairs to those unchanged heads.

This is a review sequence, not an automatic merge sequence. Every proposal remains a draft. Rebase/integration must be rechecked if main or any dependency changes.

## Owner-controlled blockers and approvals

| Status | Gate | Required evidence / action |
|---|---|---|
| VERIFIED | Source/test foundation | See [CI repair](ci-repair-report.md), [security integration](security-integration-report.md), [paper acceptance](paper-trading-acceptance.md), and full branch JSON |
| BLOCKED | Real Auth0 tenant and HTTPS ingress | Owner-approved isolated staging configuration; actual issuer/JWKS/callback/PKCE/session revocation/cookie tests; independently establish socket-peer CIDRs, not forwarded-header trust |
| BLOCKED | Durable storage and checkpoint policy | Owner-approved private mount, single writer permissions, separate protected checkpoint/key channel, backup restore/rollback tests. No keys or mounts were provisioned |
| BLOCKED | Hosted existing website boundary | Reviewed owner identity integration and same-origin BFF routing without exposing service credentials; existing ChatGPT Site has not been modified |
| BLOCKED | Physical Android/browser session | Real owner/signed-out/wrong-owner, retry, loss/HALT, network outage and accessibility/device checks. CUA tool unavailable in this managed environment |
| FAILED / reviewed | Bandit medium findings | Two fixed-origin historical public-data urllib call sites and health-only probe bind; no high findings. Scanner exit is 1 and is not represented as PASS |
| NOT_INSPECTED | Historical source/secret completeness | Branch metadata, deltas, manifests and conflicts are inventoried; exhaustive line-by-line review of every old branch and Git secret history is not complete |
| IMPLEMENTED_NOT_TESTED | Eventual hosted composition | Local dashboard and operator factory implemented, but not executed in the hosted Site/real proxy environment |
| NOT_APPLICABLE | Production/live trading/2027 evaluation | Prohibited; no such action was taken |

No additional approval is needed to review these drafts. Actual deployment, production/credential changes or infrastructure provisioning are outside this session's authorization and must stop for owner authorization. No such action was attempted.
