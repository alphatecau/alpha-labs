# v0.12 baseline audit — 7 November 2026

Recorded before implementation. Scope: additive local research/simulation foundation.

## Repository and preservation

- Main: `9d705bd1982396b19006b9abd3ec8b6a254f2972`, tree `fa6cc93506ac2d15b63653c157b70880a9ef2f5a`.
- Fresh clone; clean working tree; no repository AGENTS.md found. All 15 remote branches inventoried.
- Development starts from main on `development/global-foundation-v0.12`. No branch merges, rebases, production settings, credentials or deployment changes.

| Relevant draft/development | Inspected head | Base / findings |
| --- | --- | --- |
| PR #9 / strategy v0.8 | `6f7b893ee4c319573bc23cc633f2fae6e90f7381` | main; registered strategy rejected: BTC −2.463%, ETH −1.008%, SOL −3.808% modelled final returns |
| PR #10 / strategy v0.9 | `40f0c34d4302cbaa7c6ba1ee88ea42d61bffc38c` | v0.8; six registered and two exploratory failures; downtrend inconclusive; spot SHORT unsupported |
| Multi-asset v0.11 | `f388d9c957a8fb66236f57bb30830289744110e3` | 15 commits ahead of main, zero behind; equity sessions, corporate actions, provenance and assumed costs remain separate review scope |
| PR #11 / integrity | `63a73ff0afcf331dae130c41435ddc1cc878b61a` | v0.11; 21 ahead of main; five incremental files, 385 additions |

Other branches are historical UI, diagnostics, risk/evidence, data-ingestion and restoration work. Their refs/history remain unchanged. v0.12 uses a new package namespace and dashboard directory to avoid active research/website files. The v0.11 branch contains the v0.8/v0.9 stack; none is silently included here.

PR metadata, branch refs, full main tree, local source and the v0.8/v0.9 reports were inspected. PR #11 source patches were inspected independently of its description. The existing PR11 review was also read. Repository evidence supports the historical rejections; full raw-data runs were **not repeated** in this mission.

## Reusable capabilities and gaps

| Area | Verified baseline | Gap / decision |
| --- | --- | --- |
| Python research | CSV/UTC validation, archive custody/checksums, walk-forward diagnostics, evidence export, Decimal costs | Reuse unchanged; no profitable strategy established |
| Risk | Offline `risk/policy.py` assesses proposals and always denies execution | Preserve; add a separately named simulation authority enforcing stop-risk and durable state |
| UI | Portable `apps/sites` operator dashboard and read-only local bridge | Preserve; add `apps/dashboard/paper` as local API consumer |
| Execution/accounting | Most modules contain only NOT IMPLEMENTED docstrings | Add isolated, transactional simulation package; no real broker adapter |
| Accounts/API | API, identity, PostgreSQL migration and worker are scaffolds | Local opaque-token identity boundary and SQLite tenant partitioning first; managed identity/RLS later |
| CI/security | Research + website CI active; backend/security workflow files disabled | Add offline simulation workflow; hosted security/scalability remain unverified |

## PR #11 dependency decision

GitHub check records for exact head `63a73ff` show successful research and website jobs: runs [42334672646](https://github.com/alphatecau/alpha-labs/actions/runs/42334672646) and [42334672651](https://github.com/alphatecau/alpha-labs/actions/runs/42334672651), plus successful push counterparts. These are recorded GitHub results, not fresh local execution of that PR in this mission.

Unresolved defects: event age is not bounded; accepted submillisecond timestamps are truncated before causal comparison; mutable quotes can bypass cost validation; count fields admit fractional values; output can overwrite evidence input; missing evidence hides known negative economics. Evidence flags are self-asserted and cannot certify strategies. v0.12 does not import these helpers. New immutable quote contracts retain full timestamp precision, check event/receipt/transport age, and revalidate at consumption. No real strategy receives execution eligibility.

## Baseline verification

CPython 3.12.14; Node 24.22.1. Before implementation:

```sh
PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_*.py' -v
# PASS: 102 tests, 15.000 seconds
node --test apps/sites/tests/*.test.cjs
# PASS: 36 tests
```

Full command logs are retained during development and a machine-readable final record will be committed. No empirical profitability, licensing, account eligibility or executed-fill claim follows from these tests.

## Implementation order and acceptance

1. Frozen versioned contracts, causal quote validation and broker/mode boundaries.
2. Durable tenant-scoped store, identity checks, policy ceiling and persistent HALT.
3. Recorded specialist committee and deterministic proposal/decision pipeline; unavailable agents explicitly UNVERIFIED.
4. Atomic risk assessment plus simulated order/fill/accounting lifecycle, idempotency, reconciliation and restart checks.
5. Authenticated loopback API and responsive dashboard, independent negative/security/accounting/browser tests.
6. Reproduction, threat model, migration/operations/commercial gates, evidence and draft PR.

Success for this increment means reproducible synthetic end-to-end simulation, fail-closed unsupported/unverified strategy decisions, tenant isolation at implemented boundaries, restart-persistent HALT, and unchanged baseline research. Commercial beta, real LLM integration, production identity, real broker sandboxes and global scale require separate milestones and evidence.
