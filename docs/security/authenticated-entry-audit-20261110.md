# Authenticated staging entry-point audit — 2026-11-10

Status: **research-only; NOT approved for deployment**.

## Verified repository evidence

- Existing Render staging baseline: health-only `deployment/staging_probe.py`; preserve its configured branch and start command.
- `deployment/authenticated_staging_bootstrap.py` constructs the authenticated WSGI application only when supplied reviewed ownership, principal factory, independent restricted PostgreSQL connectors and trusted Auth0 verifier. It intentionally has no module-level `application` and no listener.
- `deployment/staging_authenticated_bff.py` provides `/auth/login`, `/auth/callback`, `/auth/logout`, `/healthz`, and read-only research routes. The health response does **not** attest Auth0, session or database readiness.
- PR #82 research security acceptance audit and the GitHub Actions authenticated read-only API run 42705612788 reported success at commit `90489faaefb07f839220eada36edf7bcba1eeff7`. These are automated tests only.
- Existing security gate: `docs/staging-authenticated-acceptance-gate-20261110.md`. Follow its restrictions.

## Required next engineering work

1. Implement an **explicit, separate** authenticated staging WSGI server entry point only after resolving and reviewing ownership/principal factory, database role provisioning, session store and verifier dependencies. Do not reuse or replace the health-only service.
2. Fail startup if any required security dependency is absent. Expose separate liveness and authenticated dependency-readiness signals; never claim authenticated readiness from the health-only response.
3. Add deterministic negative tests for absent secrets, absent database connections, unknown account, forged forwarded headers, OAuth callback replay, expired/revoked sessions, cross-account access and denial of trading endpoints.
4. Exercise role provisioning, rotation, revocation and arbitrary-SQL cross-tenant isolation on a **disposable PostgreSQL 16** instance. Never use existing staging or production database for destructive acceptance.
5. Verify Render proxy socket-peer trust with the actual deployment topology, not only synthetic headers.
6. Verify real Auth0 confidential-client login/callback/logout with two test accounts after separately authorised staging deployment.
7. Obtain independent security sign-off before promoting any authenticated deployment.

## Change controls

No merge, deployment, credentials, migrations, broker connectivity, trading execution, or GPT Site changes are authorised by this audit. The existing health-only staging probe remains the rollback baseline.

## CI interpretation

A green unit/CI run proves only the tests exercised at that SHA passed. It does not establish production proxy trust, real Auth0 acceptance, role isolation, or independent approval.
