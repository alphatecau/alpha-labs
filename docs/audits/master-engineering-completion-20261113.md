# Alpha Labs engineering acceptance · 13 November 2026

**Offline research and local Linux simulation GO. Private staging, hosted owner paper and real-money trading NO-GO.** The existing public research publication is listed as successful by Sites. A fresh public reachability sign-off is blocked because the execution environment received HTTP 403. The owner paper desk uses the external authenticated BFF architecture.

## Integration order

~~~mermaid
flowchart TD
    M["Main b973e43"] --> A["PR 103 · CI and dependencies"]
    A --> B["PR 104 · Auth0 and PostgreSQL isolation"]
    B --> C["PR 105 · Owner paper integration"]
    C --> D["PR 106 · Checkpoint and transport repairs"]
    D --> E["PR 109 · Full control-state protection"]
    E --> F["PR 110 · Free local multi-asset rehearsal"]
    G["PR 107 · Health probe"] --> C
    H["PR 108 · Local terminal and clock skew"] --> C
~~~

PRs #107 and #108 were independently integrated into the #105 branch. Both precede the latest #106 and #109 sources. The #106 head was reconciled with #105 through fast-forward updates to the draft branch, preserving both histories and the loopback-only diagnostic CLI. The health-only Render Blueprint uses its WSGI application explicitly. PR #106 was restored to draft status. Main remained at b973e4330888970184cf9f90fb9487a1ff563b3b.

The security stack incorporates the #93, #95 and #96 controls plus #94's correction to the collector from #92. #103 resolves the #100 Ruff failure without narrowing the rules. #99's quote-test change was previously verified against main. The [branch inventory](evidence/master-completion-20261113/branch-inventory.json) records 116 branches and 35 dry conflicts against main. Source review beyond related candidates remains incomplete.

## Exact source verification

Counts below come from fresh local execution on the listed source trees. CI links identify the observed GitHub workflow run at the relevant exact head.

| PR | Source SHA | Python unit | Disposable PostgreSQL | Primary CI |
|---|---|---:|---:|---|
| #103 | 0c0a99f62f8e25df6c66a74ea8447922f57ea16d | 247 + 48 subtests | — | [Backend](https://github.com/alphatecau/alpha-labs/actions/runs/43171222961) |
| #104 | f41e8c7ee43575d50771ddc4cfe96389c468243e | 460 + 207 subtests | 35 + 22 subtests | [Backend](https://github.com/alphatecau/alpha-labs/actions/runs/43174500864) |
| #105 | be2901e7582eee9636460236b2521b2fefe7a2c0 | 538 + 240 subtests | 38 + 22 subtests | [Backend](https://github.com/alphatecau/alpha-labs/actions/runs/43239398030) |
| #106 | eaafdcb0b126574e0af6be5e56034f371cf84794 | 545 + 240 subtests | 44 + 22 subtests | [Owner and Bandit](https://github.com/alphatecau/alpha-labs/actions/runs/43241208694) |
| #109 | c5fd585c87ba3776b5e2d9749b3a03e7d87c97c7 | 560 + 246 subtests | 47 + 22 subtests | [Backend](https://github.com/alphatecau/alpha-labs/actions/runs/43241574326) · [Owner and Bandit](https://github.com/alphatecau/alpha-labs/actions/runs/43241574684) |
| #110 | df81e558b3289007bc2ce816c06728dec1962df0 | 562 + 246 subtests | Inherited from #109 | [Backend](https://github.com/alphatecau/alpha-labs/actions/runs/43241881118) · [Free local paper](https://github.com/alphatecau/alpha-labs/actions/runs/43241881130) |

43 website tests passed on the #109 source tree. #110 added 2 unit cases and preserved the website and PostgreSQL code. The #110 targeted terminal suite passed 40 tests plus 31 subtests. The make research-test entry point passed 549 unittest cases. Ruff 0.15.22, Bandit 1.9.4 medium/high, dependency audit, synthetic research smoke, and git diff checks passed. GitHub CodeQL and Gitleaks passed for the security and local source heads. The #105 engineering-status audit detected moving refs and failed closed. The rerun after the refs stabilised passed. The synthetic smoke uses only the repository's named synthetic example.

Local environment used Python 3.12.14, pytest 9.2.0, psycopg 3.3.9, disposable PostgreSQL 16.2 and Node 24.22.1. The PostgreSQL tests use only the guarded disposable loopback database names and synthetic fixture credentials. No reserved evaluation data was accessed.

~~~sh
PYTHONPATH=packages/alpha_lab/src:.:tests/integration python -m pytest tests/unit -q --junitxml=unit.xml
PYTHONPATH=packages/alpha_lab/src:.:tests/integration ALPHA_DISPOSABLE_PG_CI=1 ALPHA_TEST_PG_DSN='postgresql://postgres:ci-only@127.0.0.1:5432/alpha_rls_test' ALPHA_TEST_POSTGRES_DSN='postgresql://alpha_test:local_ci_only@127.0.0.1:5432/alpha_security_test' python -m pytest tests/integration -q --junitxml=postgres.xml
PYTHONPATH=packages/alpha_lab/src:.:tests/integration python -m pytest tests/unit/test_local_multiasset_catalogue.py tests/unit/test_local_paper_terminal.py tests/unit/test_paper_runtime.py tests/unit/test_live_paper_service.py tests/unit/test_coinbase_future_clock_tolerance.py -q
node --test apps/sites/tests/*.test.cjs
make research-test
ruff check packages deployment tests scripts/engineering_status.py scripts/reconcile_repository.py
bandit -q -r packages deployment -ll -f json -o bandit.json
pip-audit --strict -r runtime-requirements.txt --format json
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output synthetic-smoke.json
PYTHONPATH=packages/alpha_lab/src:.:tests/unit python tests/acceptance/protected_paper_recovery.py --postgres-bin /path/to/postgresql/bin
~~~

The dependency audit requirements file is generated from pyproject.toml project.dependencies. The disposable recovery command builds its own cluster, exercises PostgreSQL archive restore, and stops only that cluster. The BFF and browser steps are in the [protected staging runbook](../architecture/protected-paper-staging-acceptance.md). The updated [37-row evidence matrix](independent-staging-acceptance-20261112.md) records environment, exact source and reproducibility by result.

## Verified controls and limits

- Checkpoints authenticate journal sequence and hash, cash and positions derived by deterministic replay, cost basis, loss limits, HALT and risk marks, account binding, configuration, replay nonces, order states, idempotency and transition history. One SQLite transaction commits the state. An independent PostgreSQL transaction confirms the next sequence before acknowledgement.
- Missing, stale, unauthorised, tampered or unmatched state is denied. Tested real PostgreSQL role permissions include denied table and column mutation, independent tenant roles, expired and revoked sessions, current ownership, shared quotas, concurrent checkpoint and order updates and replay.
- Tested an exact restored SQLite and PostgreSQL backup pair, stale PostgreSQL restore and actual shutdown during an interrupted order. Matching restore recovered one fill and stayed halted. Interruption returned CHECKPOINT_HALT with HTTP 503. Restart rejected the unmatched pair. A coordinated rollback of both stores can reproduce an older valid pair. Hosted recovery requires an independently retained current receipt and separate custody.
- Owner browser routes share PostgreSQL quota and session checks with the research BFF. Tests reject forged headers, forged identity, duplicate cookies, replayed OAuth state and forged CSRF. Synthetic auth tests do not establish the real Auth0 tenant, endpoint or proxy configuration.
- Public downloads pin origins, reject redirects and unexpected media types or framing, and enforce bounded time and bytes. The quote feed rejects malformed, stale and regressing books, pauses after rate limits and defers quotes ahead of the local clock until they are causal. Coinbase public books were observed for BTC-USD, ETH-USD and SOL-USD at 2026-11-12T14:46:01–03Z. A disposable Linux terminal session simulated a SOL buy and sell and recovered exactly two fills after restart.
- Default market orders fill against sufficient displayed depth or reject. Limit orders support persistent pending, partial, filled, rejected and cancelled states, price bounds and stable retries. Buy stops, daily and portfolio HALT, long-only USD balances and deterministic exposure controls apply. The five US ETFs were exercised using deterministic synthetic quotes and explicit session windows. Live US/ASX quotes and other catalogue symbols remain disabled.
- Chromium blocked AF_UNIX socket creation before rendering. The headless-shell download also failed in this environment. JavaScript controller and loopback HTTP tests passed. Physical Android and hosted browser results remain blocked. The manual Android checklist is executable in the staging runbook.

## Operational blockers

| Owner | Cause and impact | Required resolution |
|---|---|---|
| Storage and recovery operator | Hosted independent checkpoint and key custody, durable single-writer mount and protected backups remain unverified | Establish an independent current receipt and repeat the matching/stale restore and outage exercise in the isolated hosted environment |
| Auth0 administrator | Real client/issuer/callback, owner and second account and natural expiration have no acceptance evidence | Exercise real Auth0 PKCE, JWKS, owner access, denial, expiry and revocation using approved staging bindings |
| Render and ingress operator | The existing Render service reports health only and its owner-paper route returned 404 | Verify isolated TLS peer/header boundary, readiness probes, sign-in abuse controls and exact release pin |
| Android QA and owner | Managed Chromium and physical Termux/Chrome acceptance are blocked | Run the loopback harness where Chromium can start, then run the manual checklist on the physical Android device |
| Market-data owner | US/ASX entitlement, provider timestamps, corporate actions, calendars and FX are unverified | Verify a permitted feed and market metadata before enabling each additional instrument |
| Sites owner | The existing public publication reports version 2. Versions 3 and 4 are saved. A fresh anonymous request returned HTTP 403 in this environment. | Verify research-only access from an independent network. Keep private paper routes on the authenticated BFF. |
| Release owner | Hosted gates and independent review are open | Complete the gates and obtain the separately authorised release decision |

Render inventory identified an available free PostgreSQL 16 instance with a 9 December 2026 expiry. The current Render /healthz probe returned research_only and trading disabled. These observations do not qualify the instance for checkpoint custody or paper hosting.

## Readiness

| Use | Decision | Verified scope |
|---|---|---|
| Offline research | GO | Tested source trees and synthetic research path |
| Local simulated paper trading | GO | Linux Coinbase spot session and synthetic US ETF profile. Physical Termux pending. |
| Private staging | NO-GO | Real Auth0, HTTPS proxy, independent storage and device gates |
| Public research dashboard | NO-GO for fresh access sign-off | Existing version 2 publication is reported successful. Independent anonymous access remains unverified. |
| Hosted owner-only paper trading | NO-GO | Full protected deployment acceptance and custody required |
| Real-money trading | NO-GO | Simulated execution scope |
