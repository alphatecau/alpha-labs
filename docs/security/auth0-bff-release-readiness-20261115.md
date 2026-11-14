# Alpha Labs — Auth0 BFF Security Acceptance and Release Readiness

**Evidence baseline:** PR #122–#127 merged to main; new failure-path acceptance is proposed in this PR and is not counted as passing until CI confirms it.

## Objective and architecture

Research-only authenticated WSGI BFF; Auth0 authorisation-code + PKCE; one-time durable OAuth state; server-side opaque sessions; owner authorisation; per-tenant restricted PostgreSQL LOGIN roles with FORCE RLS; read-only research endpoints. No trading endpoints are exposed by this BFF.

## Verified repository evidence (prior merged PRs)

| Gate | Evidence | Status |
| --- | --- | --- |
| Auth0 signed token validation | RS256, nonce, audience, issuer, time-claim regression | CI passed on merged PRs |
| OAuth state replay and sessions | Disposable PostgreSQL 16 replay, expiry, revocation, rollback | CI passed on merged PR #125 |
| Integrated BFF routing | Real PostgreSQL state/sessions; injected Auth0 exchange and tenant SQL | CI passed on merged PR #126 |
| Tenant role isolation | Actual PostgreSQL 16 restricted logins, FORCE RLS, role/write denial, drift rejection | CI passed on merged PR #127 |
| Failure paths | Session/ownership/tenant outage, invalid callback, revocation | Pending CI in this PR |

## New failure acceptance and expected results

- Session store unavailable -> 503, no research payload
- Ownership verification unavailable -> 503, no research payload
- Tenant credentials revoked -> 403, no research payload
- Research database unavailable -> 503, no research payload
- Auth0 token exchange failure -> 401, no session issued
- Malformed OAuth callback -> 401, no token exchange
- Revoked owner -> immediate 403; explicit reprovisioning restores access

The new tests inject controlled failures while using disposable PostgreSQL for session and OAuth state. They do not reproduce a real network partition or a process crash.

## Outstanding blockers

1. Real Auth0 tenant login and browser callback, including both test users and session expiry.
2. Dedicated isolated hosted PostgreSQL with securely provisioned tenant roles and trusted credentials.
3. Actual tenant SQL access through the hosted service; the integrated BFF test uses an injected research connector.
4. Independent security review, including threat modelling, CSRF, cookie/session, JWKS rotation, network boundaries and least-privilege grants.
5. Operational recovery and production observability evidence.
6. Explicit release authorisation and separate live-capital trading gates.

## Release decision

**NO-GO** for hosted production and live trading. Passing CI is necessary but not sufficient. No paid resources, existing Render deployments, hosted database, production credentials or live trading are changed by this PR.
