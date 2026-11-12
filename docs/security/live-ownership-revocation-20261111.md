# Per-request ownership revocation repair and disposable PostgreSQL audit

Base: PR #84 head `4eafca676da18f015ae40c21c72e7849b90ad594`.
Branch: `research/auth-ownership-revocation-20261111`.
Research only; no deployment, merge or production acceptance is authorized.

## Verified defect and repair

The original BFF returned `200 OK` with private synthetic research after the
actual ownership registry had revoked the principal. Ownership was checked at
login, but protected reads only resolved an unexpired session.

Require an explicit trusted `authorize_owner` callback in the BFF and
`require_owner_id` on the supplied registry. Both read routes validate the full
session-derived owner digest and require an explicit True decision before any
reader/credential access. Revocation or unknown ownership returns 403; registry
outage returns 503 without data. Bootstrap rejects missing authorization before
verifier/network initialization. Browser owner headers/queries cannot select
authorization identity.

SQLite and PostgreSQL adapters reuse their existing active-ownership table and
parameterized lookup; no schema changes or auto-migrations. The opaque-session
hash now preserves the canonical issuer slash to match the verifier/registry,
reusing the fix already proposed in #87. Existing research sessions using the
old hash fail closed and require login again. Any external owner/credential
mapping needs separate review before deployment; none was changed here.

Revocation applies to subsequent authorization checks after its transaction
commits. A read already authorized before revocation may finish; no atomic
cross-store revocation guarantee is claimed.

## Executed verification

Python 3.12.14, cryptography 46.0.7, psycopg 3.3.8, Node 24.22.1. The local
PostgreSQL 16 container is newly created, labeled for this task, loopback-only,
with tmpfs storage. Its synthetic test-role passwords are public fixtures, not
external credentials. No configured application database or credentials used.

The commands below exited 0 on the repaired tree. Final commit/CI URLs are
recorded in the accompanying draft PR.

```sh
PYTHONPATH=packages/alpha_lab/src /tmp/alpha-audit-venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py' -v
node --test apps/sites/tests/*.test.cjs
PYTHONPATH=packages/alpha_lab/src /tmp/alpha-audit-venv/bin/python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output /tmp/auth-synthetic-smoke.json
git diff --check
```

396 Python tests and 36 website tests passed; synthetic smoke passed. The full
suite includes eight new BFF/registry negative tests and a PostgreSQL lookup
contract test, plus the existing signature, JWKS recovery, state, nonce, PKCE,
session, proxy and forged-identity regressions. A dedicated auth subset of 40
tests also passed on the original source; this did not detect revocation.

For each integration pattern listed below, execute:

```sh
ALPHA_DISPOSABLE_PG_CI=1 ALPHA_TEST_PG_DSN=postgresql://postgres:ci-only@127.0.0.1:5432/alpha_rls_test PYTHONPATH=packages/alpha_lab/src:.:tests/integration /tmp/alpha-audit-venv/bin/python -m unittest discover -s tests/integration -p PATTERN -v
```

| Pattern | Tests | Result |
|---|---:|---|
| `test_staging_ownership_revocation.py` | 3 | PASS: actual opaque sessions, independent registry instances, committed revocation, expiry, user/issuer separation, denied cross-store role access |
| `test_bff_postgres_chain.py` | 3 | PASS: existing two-user chain, reused connection resets on commit/rollback, explicit reproduction of the shared-GUC limitation |
| `test_auth_postgres_durable.py` | 4 | PASS: session lifecycle, expiry, one-use state, eight concurrent consumers with exactly one winner |
| `test_account_role_isolation.py` | 3 | PASS: tenant-role isolation under forged GUC/arbitrary SQL, denied role switching and writes |

Additionally, six `test_postgres_paper_security_real.py` tests passed using
`ALPHA_TEST_POSTGRES_DSN=postgresql://postgres:ci-only@127.0.0.1:5432/alpha_security_test`
in the same new disposable container and `PYTHONPATH=packages/alpha_lab/src`.
Thirty-two concurrent limiter attempts admitted exactly 12, and independent
limiter instances enforced the same shared limit. The legacy test's explicit
migration ran only in that disposable database.

All three SQL fixtures exited 0 using the container-local psql with
`-v ON_ERROR_STOP=1 -U postgres -d alpha_rls_test`:
`research_rls_isolated.sql`, `research_rls_transaction_fixture.sql`, and
`research_role_isolation_fixture.sql`. A passing limitation-reproduction test
does not establish that the legacy shared-reader design is secure.

## Remaining gates and task card

- HIGH: a shared reader can set another owner's GUC; retain distinct restricted
  database LOGIN roles when arbitrary-SQL isolation is required.
- The current BFF still lacks the older chain's shared identity rate limiter.
- Real Auth0 browser exchange, JWKS rotation against an actual tenant, Render
  proxy topology, operational pool configuration and real provisioning remain
  unverified. Existing #86/#87 extraction work is preserved.
- This is an internal source review and executable regression evidence, not
  independent human approval. Merge/deployment and any external credential or
  database changes require separate owner authorization.

Objective: revoke subsequent reads without waiting for session expiry.
Dependencies: PR #84 stack; reuse #87's canonical hashing contract. Owned scope:
BFF/bootstrap/assembly, two ownership adapters, opaque-session hash, their call
sites/regressions and existing CI. No schema migration. Rollback: revert the
isolated commit. Stop on production dependencies, conflicts, unavailable
authorized access or budget exhaustion. No live trading, broker calls, external
credential changes or reserved 2027 dataset access.
