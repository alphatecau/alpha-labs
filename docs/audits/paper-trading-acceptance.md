# Owner paper acceptance — 2026-11-12

Overall: VERIFIED for the executed offline/disposable scope; BLOCKED for staging acceptance. No order endpoint has been exposed, no hosted website has changed, and no deployment or broker request occurred.

## Scope and dependencies

Research branch `research/master-integration-20261112` reuses main `b973e4330888970184cf9f90fb9487a1ff563b3b` / merged #98, security draft #104 `f41e8c7ee43575d50771ddc4cfe96389c468243e`, and existing #101 `f9eff55b995ac799877279752c3294eb4d69e202`. It preserves `PaperRuntime`, journal, ledger, deterministic risk engine, quote adapters and research routes. New composition: `deployment/owner_paper_bff.py`; private local assets: `apps/sites/owner-paper/`. No second accounting or trading engine was created.

Task card: objective is safe owner-only simulated order integration. Owned files are the paper session/journal/feed, owner BFF, private dashboard, acceptance tests/workflow and audit reports. Expected behavior is fail-closed identity/data/persistence handling with exactly-once simulated order identity. Rollback is closing an unmerged draft; no live state was changed. Stop at any deployment, real credential/configuration change, protected data access or live broker action. All destructive tests use synthetic fixtures in temporary files or the explicitly guarded disposable PostgreSQL container.

## Verified controls and repairs

| Status | Area | Evidence / behavior |
|---|---|---|
| VERIFIED | Existing engine and accounting | PR #101 replay/checkpoint/FIFO P&L implementation reused; main's exclusive POSIX journal writer lock retained |
| VERIFIED | Atomic simulated fills | SQLite `BEGIN IMMEDIATE`, full synchronization, candidate ledger published only after durable append, hash-chain/replay reconciliation |
| VERIFIED | Database order uniqueness | Unique index on a generated JSON order ID; migration preserves original payload/hash bytes; malformed identity schema and duplicate JSON members rejected |
| VERIFIED | Concurrent duplicates | 32 offline owner requests produce one fill; real PostgreSQL quota across two BFF instances admits seven of 16 simultaneous requests, producing one fill and nine 429 responses |
| VERIFIED | Process interruption | Separate spawned processes terminate immediately before commit (exit 73) and after committed append but before memory publication (exit 74); restart respectively recovers zero and one fill; retry after restart returns ALREADY_COMMITTED |
| VERIFIED | Conflicting IDs / contention / tampering | Different terms for an existing ID rejected; raw concurrent SQLite inserts enforce uniqueness; locked DB returns 503/HALT with no partial fill; hash, sequence, payload and independently sealed-checkpoint adversarial tests pass |
| VERIFIED | Owner boundary | Existing durable OIDC session and current ownership authorizer resolve the pinned internal owner; browser account/owner headers confer no access; wrong owner cannot obtain HTML/assets, state or fills |
| VERIFIED | Session/CSRF/replay | Session-bound HMAC CSRF plus exact same-origin POST; duplicate JSON/body limits; stale arm revision cannot reverse HALT; repeated order IDs do not refill; watchdog checks the arming session's expiry/revocation/current ownership |
| VERIFIED | Shared quota | Research, state, arm and orders share existing PostgreSQL account quota; alternate paper aliases rejected. Authenticated CSRF-protected emergency HALT is quota-exempt, exposes no portfolio/history and cannot place orders |
| VERIFIED | Fail-closed outages | Identity/quota/database failures halt; feed HTTP/protocol failures invalidate books; separate health watchdog halts stale books while a network poll is blocked |
| VERIFIED | Risk and persistence | USD 10,000 virtual start; BUY/SELL, cash/positions, simulated fees/slippage, bid valuation, realised/unrealised FIFO P&L, stop metadata, depth/risk/cash checks, persisted daily-loss/drawdown HALT and manual emergency stop; restart always starts halted |
| VERIFIED | Relay hardening | Old HMAC-only `live_paper_api:create_app()` startup disabled; legacy class remains solely for compatibility tests. The owner factory mounts the durable OIDC boundary instead |
| VERIFIED | API ingress tests | Explicit reviewed proxy CIDRs required; unrestricted CIDR, wrong socket peer and spoofed forwarded chains rejected. No module-level app/listener or default secret |
| VERIFIED | Private dashboard logic | Android-oriented responsive layout, bid/ask and freshness, virtual portfolio/positions/P&L, confirmed BUY/SELL, history, arm/HALT; Node tests exercise freshness, denied storage, API outage, CSRF transport, confirmation cancellation and stable retry IDs |
| BLOCKED | Browser/device QA | No real browser or Android session was executed. Node controller tests are not visual/device acceptance |

The paper factory supports **one owner and one ledger writer process**, with serialized threaded requests. Two BFF objects in a test share that one paper session; this is not proof of horizontally replicated paper ledgers. Shared PostgreSQL limits across processes are separately exercised by the security integration tests.

## Actual public-market observation

VERIFIED: read-only fixed-origin Coinbase Exchange level-one GETs succeeded for BTC-USD, ETH-USD and SOL-USD at approximately `2026-11-12T07:35:33Z`. All three books passed bid/ask, size, event sequence, UTC exchange-event timestamp and ten-second freshness validation when observed. Exact returned evidence: [live-market-observation.json](live-market-observation.json). These are historical observations, not current quotes, forecasts, guaranteed availability or trading results. No USD/USDT/AUD conversion is performed. Requests are bounded to 8-second network timeouts and 8,192-byte response bodies; redirects and unexpected origins are rejected. Repeated polling recovers healthy books after transient failures; execution remains manually halted after a data HALT.

## Executed commands and results

Python 3.12.14, SQLite supplied by that runtime, PostgreSQL 16.15, cryptography 50.0.2, Ruff 0.15.22. Executable prefix `/tmp/alpha-audit-venv/bin/`; `PYTHONPATH=packages/alpha_lab/src:.:tests/integration` for Python acceptance commands.

| Status | Exact command (with prefix/environment above) | Exit | Result |
|---|---|---|---|
| VERIFIED | `python -m pytest tests/unit -q --junitxml=/tmp/master-integration-unit.xml` | 0 | 518 passed + 230 subtests; 748 JUnit cases, zero failures/errors/skips |
| VERIFIED | `ALPHA_DISPOSABLE_PG_CI=1 ALPHA_TEST_PG_DSN=postgresql://postgres:ci-only@127.0.0.1:5432/alpha_rls_test ALPHA_TEST_POSTGRES_DSN=postgresql://alpha_test:local_ci_only@127.0.0.1:5432/alpha_security_test python -m unittest discover -s tests/integration -p 'test_*.py' -v` | 0 | 38 actual-database tests, no skips |
| VERIFIED | `node --test apps/sites/tests/*.test.cjs` | 0 | 42 passed, zero skipped |
| VERIFIED | `python -m alpha_lab.cli examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic --output /tmp/master-integration-smoke.json` | 0 | Synthetic offline smoke; no reserved dataset or profitability claim |
| VERIFIED | `ruff check packages deployment tests scripts/engineering_status.py scripts/reconcile_repository.py` | 0 | All selected rules, no blanket exclusions |
| VERIFIED | `/tmp/actionlint -shellcheck='' -pyflakes=''` | 0 | Workflow schema/expression validation; optional shellcheck/pyflakes analyzers not installed |
| VERIFIED | `/tmp/gitleaks dir --redact --exit-code 1 --no-banner .` | 0 | No secret findings in working tree; not an exhaustive historical secret audit |
| VERIFIED | `pip-audit --strict -r /tmp/master-integration-runtime.txt --format json` | 0 | Requirements generated directly from pyproject; zero known runtime dependency vulnerabilities |
| FAILED / reviewed | `bandit -q -r packages deployment -ll -f json -o /tmp/master-integration-bandit.json` | 1 | Three medium findings: two historical urllib adapters (B310) and existing health-probe wildcard bind (B104); zero high findings. No scanner rules were suppressed |
| VERIFIED | `git diff --check` | 0 | No whitespace errors |

Local logs are `/tmp/master-integration-{unit,pg,website,gitleaks}.log`. CI artifacts are the durable review evidence. The new `owner-paper-acceptance.yml` starts its own disposable PostgreSQL service and rejects missing/skipped test evidence. Final published commit and current CI URLs are recorded in the draft PR; reports cannot embed their own eventual commit hash.

## Failed attempts and limits

- FAILED: combined `pytest tests/unit tests/integration` initially exited 2 because existing unit/integration files share a module basename. Executing the unit pytest suite and integration unittest discovery separately resolves collection without excluding tests.
- FAILED while authoring tests: a synthetic provider timestamp omitted `Z`; a squash-equivalence fixture accidentally recreated an identical commit; an HTTP fixture tried to decode an empty 429 body. The fixtures were corrected and the full suites above rerun. These failures are not reported as passing runs.
- BLOCKED evidence, not PASS: running PostgreSQL pytest without its required environment produced three skips; that result was rejected. All 38 integration tests were subsequently executed against the disposable database. A dependency audit initially referenced a nonexistent temporary requirements file (exit 1); requirements were regenerated from pyproject and the verified audit rerun.
- BLOCKED: real Auth0/proxy/cookie interoperability, protected persistent mounts, broker credential separation and independent checkpoint/backup policy require owner-controlled infrastructure. No production-grade claim follows from these tests.
- BLOCKED: protected external checkpoints are implemented/tested in the reused runtime, but are not provisioned for the operator composition. Hashes stored with the same writable journal do not detect complete malicious rewrite/rollback. The local filesystem and control table must be restricted to the one trusted owner service.
- BLOCKED: existing hosted ChatGPT Site native identity/server integration is unavailable. This proposal adds private assets behind the repository BFF and leaves the hosted website unchanged and integration disabled.
- BLOCKED: Sites [SKILL.md](skill://plugin_connector_1p_689987207de08191979cf68eca2941c6/sites/SKILL.md) states, “If `cua_repl.js` is unavailable, skip browser QA: do not start a preview server, install a browser, or improvise another browser-control path.” It is unavailable here; therefore no preview, screenshot or physical Android acceptance is claimed.
- NOT_INSPECTED: exhaustive source security review of all historical branches, historical secret scanning and future exchange availability.
- NOT_APPLICABLE: production migration, hosted-site publication, real-money execution and reserved 2027 evaluation data. None was accessed or enabled.

Do not expose the order API until independent review and the remaining owner-controlled staging acceptance gates are complete.

## Published first-head evidence and final snapshot

Draft [#105](https://github.com/alphatecau/alpha-labs/pull/105), first source head `85b53738cf1489e4ccae5357501bddc1763a06e0`: eight exact-head workflow runs succeeded. [Owner acceptance 43177455781](https://github.com/alphatecau/alpha-labs/actions/runs/43177455781) decoded logs verify 18 tests plus two crash-boundary subtests, including actual PostgreSQL owner/quota cases. [Backend 43177455758](https://github.com/alphatecau/alpha-labs/actions/runs/43177455758) verifies the then-current 517 tests plus 230 subtests (747 JUnit cases, no skips). A subsequent audit regression test increases the final local unit total to 518, and the final CI head is recorded separately in the PR.

The final repository inventory includes all 110 remote branches and 75 open PRs observed before the concluding audit commit. Its own branch row correctly identifies the observed first head above; an artifact cannot contain its own eventual commit hash. No other observed branch head changed in that refresh. Final CI must be matched to the subsequent published head, not inferred from the first-head checks.

The concluding integration explicitly pins checkout to `github.event.pull_request.head.sha || github.sha` in 19 workflows and disables persisted checkout credentials. Existing explicit manual input refs remain explicit and are classified as unverified checkout targets by the evidence collector. The reconciliation policy rejects count mismatches, wrong heads, partial retrieval, pending/skipped evidence and manual events as a basis for READY_FOR_REVIEW. It preserves the original evidence instead of converting absence to PASS.

Evidence labels: VERIFIED = observed/executed; IMPLEMENTED_NOT_TESTED = code without applicable acceptance; FAILED = executed failure; BLOCKED = missing dependency/authority/evidence; NOT_INSPECTED = no examination; NOT_APPLICABLE = outside scope.
