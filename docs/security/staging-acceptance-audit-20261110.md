# Alpha Labs — independent-review preparation and staging acceptance audit

Date: 2026-11-10. Scope: merged PR #81 research code, Render staging configuration, disposable PostgreSQL verification. **Release decision: NO-GO.** This is an engineering pre-review, not an independent security certification.

## Directly inspected
- PR #81 authenticated bootstrap exists on `research/postgres-rls-transaction-hardening-20261110`; this branch is ahead of `main`, not a production release.
- Render service `srv-dbop6f3bc2fs73cqfksg` still targets `research/render-safe-staging-entry-20261109`, with auto-deploy disabled and `python deployment/staging_probe.py` as its start command.
- Render PostgreSQL `dpg-dboq4j7f3r2c73bvlif0-a` is available, PostgreSQL 16, Singapore, and has an empty external IP allowlist. **Do not use this database for disposable role-rotation tests.**
- `deployment/authenticated_staging_bootstrap.py` has no WSGI `application` symbol or server runner by design. It requires trusted ownership/principal factories and three restricted connectors.
- `deployment/disposable_tenant_role_provisioning.py` refuses databases other than `alpha_rls_test`; the isolated GitHub Actions workflow uses a disposable PostgreSQL service and runs RLS/role/rotation tests.

## Outstanding blockers
1. Implement a reviewed, executable WSGI entry point with a strict trusted-proxy boundary. Do not change Render's start command until validated.
2. Specify, provision and independently verify least-privilege OAuth state, session and per-tenant reader database roles. Distinct credential lifecycles and no superuser fallback.
3. Demonstrate password rotation/revocation against a disposable `alpha_rls_test` database, then independently review SQL grants and tenant role memberships.
4. Complete real Auth0 login, callback, logout, expiry, replay and two-account isolation tests; synthetic CI tests do not prove the tenant integration.
5. Obtain a reviewer independent of the code author to inspect issuer/JWKS rotation, CSRF, trusted proxy, session persistence, SQL permissions, secret handling, observability and fail-closed behaviour.
6. Only then request explicit staging approval and provision protected Render secrets. Keep research-only endpoints; no trading execution or GPT Site modification.

## Security concerns requiring targeted review
- `RefreshingAuth0Verifier` refresh is periodic, not explicitly triggered by an unknown key ID. Confirm acceptable key-rotation recovery latency and test failure/recovery.
- The authenticated BFF currently issues a session cookie with a 30-minute maximum age. Verify server-side expiry and revocation in a real two-worker environment.
- The bootstrap has no approved ownership registry or production-grade connection factories wired; importing it does not start an authenticated service.
- Validate whether PostgreSQL's `default_transaction_read_only` is enforced as expected and cannot be overridden by the tenant login role; rely on independently verified SQL privileges and RLS, not that setting alone.

## Evidence required for GO
- Exact reviewed commit SHA and passing latest CI, including isolated PostgreSQL acceptance.
- Signed independent security-review outcome with critical/high findings closed.
- Disposable DB role creation, tenant cross-access denial, old-password revocation and new-password access evidence.
- Auth0 browser tests across two independent accounts with logs redacted.
- Confirmed Render configuration, health endpoint, restricted service permissions and explicit deployment authorisation.

**No deployment, merge to main, real credential rotation, database migration or trading enablement is approved by this document.**
