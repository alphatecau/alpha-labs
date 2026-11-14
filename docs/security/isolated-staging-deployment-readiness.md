# Isolated Auth0 Staging — Deployment Readiness and Recovery Runbook

**Scope:** Planning and offline verification only. This document does not authorise a deployment or paid infrastructure.

## Hard isolation requirements

- Create a **new** staging service and a **new** isolated PostgreSQL database. Never repurpose the existing `alpha-labs-k869.onrender.com` health-only service or its database.
- Select `deployment.isolated_auth0_wsgi:application` only for the new service.
- Configure `ALPHA_ISOLATED_STAGING=true` only after independently validating the target hostname, role grants, dedicated database and explicit owner approval.
- Supply Auth0 client secret and all database credentials through server-side secret storage. Do not commit them, paste them into issues or log them.
- Provide separate runtime DSNs for OAuth state, sessions and ownership; an independent audit DSN; and a restricted tenant credential mapping. The application audits role identity and grants at startup.
- Enforce HTTPS and exact Auth0 allowed callback `https://<isolated-host>/auth/callback`. Configure allowed logout and web origins to the same isolated host.
- All tenant research connections must use distinct restricted LOGIN roles, read-only transactions, FORCE RLS and no role-switch privileges. The current BFF does not expose trading actions.

## Preflight — no network or paid service required

1. Confirm the merged baseline includes PRs #122–#128 and all required CI jobs are green.
2. Run `python -m unittest discover -s tests/unit -p 'test_isolated_staging_readiness.py' -v` with repository dependencies installed.
3. Inspect the configuration validation and runtime-role audit source. Record SHA and reviewers.
4. Ensure staging secrets are absent from the repository, workflow logs and pull request comments.
5. Verify rollback plan and access to the previous immutable image/commit before deployment.
6. Confirm a dedicated isolated database is available **without violating the AUD $0 constraint**. If not, stop; no shared database fallback.

## Hosted smoke-test acceptance (only after separate authorisation)

1. Deploy to the dedicated staging service with trading disabled; verify `GET /healthz` returns 200 and `{"status":"ok","trading":"disabled"}`.
2. Complete a real Auth0 browser login with a provisioned owner; inspect HTTPS, PKCE, state binding, Secure/HttpOnly/SameSite cookies and absence of credentials in browser storage.
3. Verify callback replay and malformed state fail; expired and revoked sessions deny research.
4. Test two independent owners with separate PostgreSQL roles; verify no cross-tenant reads, writes, impersonation or role changes.
5. Confirm an unprovisioned account fails closed and missing/revoked credentials cannot fall back to a privileged role.
6. Simulate database unavailability and restore it; verify 503 without sensitive payloads and recovery without bypassing authentication.
7. Verify CSRF/origin protection for logout, response security headers, logs without secrets and operational alerting.
8. Collect signed evidence: deployment SHA, exact test environment, request/response status, role audit, independent reviewer and timestamps.

## Rollback procedure

- **Trigger:** Unexpected 200 for unauthorised research, cross-tenant result, credential leak, role-audit failure, session replay or uncontrolled 5xx.
- Immediately disable external traffic to the **new isolated** staging service. Do not change the existing health-only service.
- Revoke affected staging secrets and sessions through approved credential procedures; preserve redacted logs and incident evidence.
- Restore the last known-good immutable staging release only after verifying its configuration and role audit. If verification fails, keep the new staging service offline.
- Repeat owner login, cross-tenant denial and health smoke tests before reopening staging.
- Do not delete databases, destroy evidence, change production credentials or enable live trading as part of rollback.

## Verification gates and ownership

| Gate | Acceptance | Current status |
| --- | --- | --- |
| Offline Auth0, PostgreSQL and failure tests | GitHub Actions green | PRs #122–#128 merged with passing CI |
| Isolated configuration negative tests | New PR CI green | Pending |
| Dedicated staging service/database | Provisioned and role-audited | Blocked by isolation/budget |
| Real browser Auth0 | Two users, state/replay/expiry and cookies verified | Not executed |
| Real hosted RLS | Both tenants isolated with actual SQL | Not executed |
| Rollback and recovery | Demonstrated, recorded | Not executed |
| Independent security review | Signed review and remediation | Not executed |

**Decision: NO-GO for production and live trading.** Do not claim hosted readiness based on offline CI. Require explicit approval before provisioning any resource, even a free one, or changing deployment settings.
