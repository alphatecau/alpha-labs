# Alpha Labs — Hosted Authentication, Tenant Isolation and Independent Review

**Scope:** Research-only BFF; no live trading. **Budget:** AUD $0. **Status:** Acceptance plan and preliminary code inspection, NOT independent sign-off.

## Environment and hard boundaries

Existing Render workspace contains the health-only Alpha Labs service and one free PostgreSQL 16 database. Do not change either. The existing database expires on 9 December 2026. There is no confirmed separate isolated hosted database/service available. Do not claim real hosted acceptance on the basis of disposable GitHub Actions databases.

The Auth0 tenant must be tested through a dedicated non-production callback origin. Do not add an untrusted callback URL to a production Auth0 application or disclose client secrets in GitHub.

## A. Real Auth0 browser acceptance

**Prerequisites:** dedicated isolated HTTPS host and database; dedicated Auth0 test application/credentials; two separately provisioned test identities; HTTPS access; reviewer evidence capture. Do not proceed while missing.

| ID | Test | Pass condition |
| --- | --- | --- |
| AUTH-01 | Login from clean browser, follow Auth0 redirect and callback | Valid state/PKCE, 303, secure opaque session; research access only to provisioned owner |
| AUTH-02 | Repeat callback or replace state/cookie | 401, no second session |
| AUTH-03 | Alter nonce, issuer, audience or token signature in controlled tests | 401, no session |
| AUTH-04 | Clear state cookie, disable cookies, use cross-browser callback | 401, no session |
| AUTH-05 | Expire/revoke session and deprovision owner | Immediate 401/403, no research payload |
| AUTH-06 | Verify cookies and headers in browser developer tools | Secure, HttpOnly, SameSite; no credentials in storage, URL, logs |
| AUTH-07 | Simulate OAuth state-store and Auth0 exchange outage | Controlled failure, no session and no leaked traceback |

**Evidence:** timestamp, deployment SHA, redacted HTTP status/headers, screenshots of browser security settings (no secrets), Auth0 configuration review, tester and environment.

## B. Database isolation acceptance

Provision separate restricted OAuth, session, ownership and audit roles plus two tenant-specific LOGIN roles in a dedicated PostgreSQL 16 database. Confirm FORCE RLS and deny direct writes/role switching for reader roles.

| ID | Test | Pass condition |
| --- | --- | --- |
| DB-01 | Connect with each runtime DSN | session_user/current_user equal audited role |
| DB-02 | Query tenant A as A and B | A sees only A; B cannot read A |
| DB-03 | Query tenant B as B and A | B sees only B; A cannot read B |
| DB-04 | Attempt INSERT/UPDATE/DELETE and SET ROLE | Denied to research readers |
| DB-05 | Revoke tenant role and repeat read | 403/503, no privileged fallback |
| DB-06 | Stop DB connections then restore | 503 during outage, normal authorisation after recovery |
| DB-07 | Alter RLS/grants in a disposable fixture | Startup role audit rejects drift |

Capture SQLSTATE, role identity, policy/grant snapshots and redacted outcomes. Do not run destructive role changes on the existing Render database.

## C. Preliminary code inspection — NOT independent review

Source inspected on main: `deployment/staging_authenticated_bff.py`, `deployment/isolated_auth0_wsgi.py`, and the staging runbook.

- **Finding F-01 (operational, requires testing):** `/auth/login` calls `flow.begin()` without a surrounding failure handler. An OAuth state-store outage can surface an unhandled WSGI exception rather than a controlled 503. Add a regression test and fail-closed error response before hosted approval.
- **Finding F-02 (review required):** `/auth/callback` catches all controller exceptions and returns 401. This avoids leaking details but conflates infrastructure failures and invalid credentials. Confirm operational monitoring records safe internal error categories without exposing tokens.
- **Finding F-03 (review required):** logout checks exact Origin and uses POST, but an independent reviewer must assess CSRF behaviour when Origin is absent, SameSite cookie settings and reverse-proxy header handling.
- **Finding F-04 (review required):** isolated staging configuration checks distinct DSN strings and role identity, but independent review must verify actual database separation, least-privilege grants and tenant-role policy semantics in the hosted environment.
- **Finding F-05 (operational blocker):** no dedicated isolated hosted service/database has been verified. No real hosted Auth0 login or tenant SQL acceptance can currently be claimed.

These are review leads, not claims of exploitable vulnerabilities.

## D. Independent security review package

A reviewer who did not author the implementation should:
1. Inspect Auth0 PKCE, callback, state, JWKS validation, session lifecycle, CSRF, cookies and proxy trust boundaries.
2. Inspect tenant credential broker, PostgreSQL role audit, FORCE RLS, SQL permissions, credential rotation and secret handling.
3. Reproduce the tests in A and B, review CI evidence and perform manual negative testing.
4. Assess threat model (cross-tenant data exposure, session fixation, replay, forged token, compromised tenant role, secret leakage, DoS and rollback).
5. Produce a dated report with reviewer identity, exact commit SHA, methodology, severity-ranked findings, remediation evidence and explicit pass/fail recommendation.

**Independence requirement:** GitHub Actions, the project owner and an AI assistant cannot self-certify this review. A separate qualified human reviewer must perform and sign off the work.

## Decision and release gates

- **Offline acceptance:** PR #129 CI passed; repository test evidence exists.
- **Real hosted Auth0:** NOT EXECUTED.
- **Real hosted tenant SQL:** NOT EXECUTED.
- **Independent security review:** NOT COMPLETED.
- **Production / live trading:** NO-GO.

Defer permanent hosting expenditure. If a genuinely isolated free temporary environment becomes available, validate resource isolation and permissions before deploying. Do not share databases or weaken security gates to fit the free quota.
