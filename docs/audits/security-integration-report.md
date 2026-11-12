# Research security integration — 2026-11-12

Status: VERIFIED for the executed local acceptance scope; BLOCKED for deployment acceptance. No production service, credential, database or hosted website was changed.

## Task and provenance

Objective: reconcile the strongest existing identity, tenant-isolation, shared-limiter and evidence-collection controls on current main. Dedicated branch: `research/security-main-reconciliation-20261112`, depending on draft #103 (`0c0a99f62f8e25df6c66a74ea8447922f57ea16d`). Main inspected: `b973e4330888970184cf9f90fb9487a1ff563b3b`.

Preserved ancestry: #93 `cf367d371ab177e41c4d88cf442a99cafedb1b2e` → #95 `2f94e82368d7cc5c2665f41d1765ead35d6dfb02` → #96 `6c5513711f42a28ee7f2552014dadecff2726a29`; #92 `6f5250b82a8242f58bfbe564c527dd233d965b8e` → #94 `6839abe3bd4f1b5bb83709b3b0b890535635649c`. Selected PKCE/URL validation from #86 `faf51b983d831d3a03ca24855952923a41478c78` is reused rather than reimplemented. Original research branches remain intact.

Owned files: imported security stack, security tests/workflows, `deployment/auth0_login_flow.py`, disposable database guard and this report. Intended behavior: fail closed on invalid identity, stale ownership, unsafe database identity, incomplete evidence and shared-quota outages. Rollback: close the unmerged draft; no live systems have been changed. Stop conditions: deployment, real credentials, reserved evaluation data, or owner-only infrastructure provisioning. Tests use temporary files, synthetic identities and one disposable local PostgreSQL container.

## Independent PR #92 review

VERIFIED by loading the actual script and test blobs at #92's SHA, independently of previous audit summaries:

- Its original 27 tests pass. Six newer adversarial test methods against that exact script produce 11 assertion/subtest failures and two errors. These are expected negative reproduction results, not a passing security gate. Command: Python `unittest` runner loading `git show 6f5250b:...` blobs and the named malformed-count, invalid-conclusion, truncated-HTTP, changed-ref and revalidation-timeout tests in `tests/unit/test_engineering_status.py`; evidence: `/tmp/master-pr92-independent.log` in the execution workspace.
- VERIFIED defects: no final current-head revalidation; malformed completed conclusions/counts can be marked complete; `http.client.IncompleteRead` can escape and prevent partial-report persistence. #94 already repairs these defects. The integration keeps #94 and its regression suite instead of duplicating it.
- Exact-SHA workflow lookup, paginated PR/run retrieval, fixed GET origin, redirect rejection, bounded requests, sanitized 403/429/timeouts, partial evidence and nonzero incomplete-collection exit are covered by the combined tests. Rate limiting fails closed; there is no unbounded retry loop. Successful collection is explicitly not successful CI or release approval.
- PR #42 head `7130307c0d20df0309b8df1883182111a76bdb4a`: offline research run [42541378983](https://github.com/alphatecau/alpha-labs/actions/runs/42541378983) FAILED. PR #76 head `529c21baf97acbad60dddb11e1c5d3f84c385662`: offline research run [42641916245](https://github.com/alphatecau/alpha-labs/actions/runs/42641916245) FAILED. Passing website jobs do not override these failures.
- VERIFIED source review: collector has no repository mutation endpoint; workflow permissions are read-only and checkout credentials are not persisted. No secret findings in the integrated working tree. Dependency/CodeQL publication permissions are scoped in #103; no deployment event or real execution path was added.

## Prioritized findings and repairs

1. VERIFIED / repaired: naive stack merging would replace main's stronger JWT parser and issuer/authorized-party checks. Main's verifier and regression tests are retained. Trusted discovery/JWKS, algorithm/signature/issuer/audience/expiry validation and opaque durable sessions remain the authority; caller-supplied account IDs do not establish identity.
2. VERIFIED / repaired: original legacy PostgreSQL integration tests accepted an arbitrary environment DSN. They now require an explicit disposable-test marker, loopback:5432 and an exact approved synthetic database/user pair before connecting. The workflow supplies the marker. The guard rejects indirect service/host/passfile configuration. No production DSN was inspected or used.
3. VERIFIED / repaired: the existing #86 flow rejects issuer/callback URL userinfo/query and malformed stored PKCE verifier/nonce values. Those stronger checks and their five additional tests are reused. State is consumed atomically; nonce, PKCE and session expiry/revocation remain mandatory.
4. VERIFIED / integrated: #95 separates tenant login roles from a privileged credential broker and uses transaction-local tenant context; role capabilities, membership, policies and pooled identity are checked. No superuser/authentication-failure fallback is admitted. #96 supplies atomic, account-scoped PostgreSQL quotas shared across BFF instances.
5. VERIFIED / repaired: imported workflows use the patched `cryptography>=50.0.0,<51` constraint from #103. Imported security sources pass the full selected Ruff rules without blanket exclusions. Formatting/import splitting and one test-only lambda conversion were checked for equivalent syntax trees.

## Executed evidence

All commands below exited 0 unless explicitly stated. Python 3.12.14; cryptography 50.0.2; PostgreSQL 16.15. Environment Python: `/tmp/alpha-audit-venv/bin/python`. Unit and integration paths include `PYTHONPATH=packages/alpha_lab/src:.:tests/integration`.

| Status | Command / check | Result |
|---|---|---|
| VERIFIED | `python -m pytest tests/unit -q --junitxml=/tmp/master-security-final-junit.xml` | 460 passed, 207 subtests passed; no skips; `/tmp/master-security-final-pytest.log` |
| VERIFIED | `ALPHA_DISPOSABLE_PG_CI=1 ALPHA_TEST_PG_DSN=postgresql://postgres:ci-only@127.0.0.1:5432/alpha_rls_test ALPHA_TEST_POSTGRES_DSN=postgresql://alpha_test:local_ci_only@127.0.0.1:5432/alpha_security_test python -m unittest discover -s tests/integration -p 'test_*.py' -v` | 35 real-database tests passed, no skips; `/tmp/master-security-pg.log` |
| VERIFIED | `psql -v ON_ERROR_STOP=1` in disposable container, each of `research_rls_isolated.sql`, `research_rls_transaction_fixture.sql`, `research_role_isolation_fixture.sql` | All three fixtures passed |
| VERIFIED | `node --test apps/sites/tests/*.test.cjs` | 36 passed; `/tmp/master-security-sites.log` |
| VERIFIED | `python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output /tmp/master-security-smoke.json` (synthetic offline fixture) | Passed; `/tmp/master-security-smoke.json` |
| VERIFIED | `ruff check packages deployment tests`; `actionlint -shellcheck='' -pyflakes=''`; `gitleaks dir . --redact --no-banner` | Passed; no secret findings |
| VERIFIED | Runtime dependency `pip-audit` using declared pyproject dependencies | Zero known vulnerabilities after #103 upgrade; not a security guarantee |

Database tests exercise actual PostgreSQL RLS, role impersonation and forged tenant settings, privileged/misbound login rejection, policy drift, cross-tenant read/write, rollback/reused connections, two-issuer identity isolation, durable expiry/revocation, one-winner OAuth state consumption, shared-quota concurrency (32 requests, seven admissions), window boundaries and database/table outages. Synthetic HTTP/JWT fixtures cover invalid signatures/issuer/audience, forged assertions, replay, CSRF and proxy trust boundaries. Mocked provider tests do not establish real Auth0 interoperability.

## Remaining acceptance gates

- BLOCKED: real Auth0 tenant/client configuration, callback/cookie behavior through the eventual trusted TLS proxy, mount permissions and credential-broker separation require owner-controlled infrastructure and secrets. No credentials were requested or modified.
- BLOCKED: hosted ChatGPT Site's reviewed server identity boundary and a real-device browser session are unavailable in this environment. Existing website is unchanged.
- NOT_INSPECTED: complete source-level security review of every historical branch; the separate reconciliation report distinguishes automated metadata/diff inspection from deep source review.
- VERIFIED with limitation: static Bandit reports two medium B310 findings in pre-existing fixed-origin historical public-data adapters; no high findings. These are not represented as a clean scanner exit. See CI repair report.
- NOT_APPLICABLE: deployment, production database migration, production role provisioning and real-money trading. None was performed.

Review sequence: #103 first, this security rollup second, the separately tested owner-paper integration last. No automatic merge or branch deletion is proposed. Passing this test scope does not authorize staging or production deployment.
