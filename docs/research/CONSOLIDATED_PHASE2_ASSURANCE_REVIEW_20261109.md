# Alpha Labs — Consolidated Phase 2 security and research-evidence review

Date: 2026-11-09. Baseline: main `e43b2e199fdaae0a1cf7cc78e660f86a0642f675`.
Review scope: draft PRs #28, #29, #30, #31, #32. This is a review record, not a production authorisation.

## Verified GitHub facts

- All five PRs are draft, open and unmerged, based on the same main commit.
- PR #28 adds explicit false approval fields in the strategy bridge, regression tests and a dedicated workflow.
- PR #29 adds Python AST/JavaScript line-scanning inventory, archive and assessment adversarial tests, accounting tests and a dedicated workflow.
- PR #30 exercises the local HTTP server's read-only and mutation boundaries.
- PR #31 tests that unonboarded keys, unknown providers and caller-supplied attestations cannot grant promotion.
- PR #32 checks synthetic independent Decimal cash, holdings, fees and liquidation NAV.
- The PR #30–#32 offline research CI runs each executed 206 unit tests successfully; their Sites workflows also passed. This is **not** independent validation of external data or all runtime routes.

## Dependency and overlap analysis

| PR | Files overlapping other PRs | Dependency | Recommendation |
| --- | --- | --- | --- |
| #28 | None directly | Existing deny-only promotion authority | Review first; keep draft |
| #29 | None directly | Existing archive, accounting and assessment interfaces | Review after #28; keep draft |
| #30 | None directly | Existing local HTTP server | Review independently; keep draft |
| #31 | None directly | Existing archive trust and evidence gate | Review independently; keep draft |
| #32 | None directly | Existing Decimal ledger reconstruction | Review independently; keep draft |

No changed-file overlap was found among the five PR patches. **Integration compatibility is not proven:** each branch was tested independently against the original main; the combined change set has not been built and tested. Do not interpret disjoint file paths as integration clearance.

## Remaining evidence gates — fail closed

### Gate A: executable entry points
Known local HTTP mutation routes have negative tests. Static Python/JS discovery does not establish exhaustive runtime routes, dynamic imports, installed console scripts, framework mounts, reverse proxies, or hosted environment behaviour. Required: enumerated route/entrypoint inventory, independently reviewed access matrix, runtime tests for every exposed method, unauthenticated and forged-identity attempts, negative outcomes with logs. **UNVERIFIED**.

### Gate B: historical archive provenance
The signed-byte verifier uses a caller-supplied trust registry with an `independently_verified` onboarding label. A label alone does not prove provider identity, independent timestamp attestation or historical availability. Required: externally acquired provider signing key fingerprint, independent trust-channel evidence, signed capture receipt bound to archive hash and UTC time, revocation/key rotation procedure, replay and timestamp manipulation tests. No independent trust material supplied. **BLOCKED**.

### Gate C: portfolio NAV and execution costs
Synthetic Decimal reconstruction and cost monotonicity passed. Required: independently sourced fills/quotes, fee schedule as-of each decision time, bid/ask and depth snapshots, slippage/impact assumptions, reconciliation across portfolio holdings and cash, drawdown and risk limits, independent benchmark and sealed holdout. No authenticated external dataset or untouched holdout was verified. **UNVERIFIED**.

## Explicit review gates

- No promotion based on green CI alone.
- No merges of #28–#32 until a combined integration branch has been built and CI-verified and independent reviewers have checked permission boundaries.
- No trading, broker integration, deployment, credential or production configuration changes.
- No claim of strategy profitability or readiness without independently reproducible cost-adjusted results.
- Unknown or missing evidence must be recorded as BLOCKED or UNVERIFIED, never PASS.

## Next engineering actions

1. Build a temporary **integration-only** branch from main; apply the five PRs in dependency order using a reviewed merge/cherry-pick mechanism; do not merge to main.
2. Run the entire test suite and dedicated workflows on the combined tree; capture commit SHA, job IDs, test counts and failures.
3. Extend static inventory to a runtime entrypoint matrix including JS and deployment manifests; fail closed for unreviewed routes.
4. Acquire trusted external archive provenance and historical capture receipts before permitting any provenance flag to become true.
5. Reconcile real source snapshots and cost evidence, and preregister an untouched holdout.

**Decision: NO-GO.** Review record only; no security or research gate is promoted by this document.
