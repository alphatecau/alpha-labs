# Branch reconciliation

Snapshot main: `b973e4330888970184cf9f90fb9487a1ff563b3b`.
Inventoried **109 remote branches** and **74 open PRs**.

Machine evidence: `branch-reconciliation.json`. Every row is an observed snapshot, not merge approval.
Original creation SHAs are NOT_INSPECTED because GitHub does not expose them; declared bases and computed merge bases are recorded.
Historical line-by-line security review remains NOT_INSPECTED unless explicitly recorded.

| Branch | Head | PRs | Disposition | CI failures | Main conflicts |
|---|---|---|---|---|---|
| `audit/day1-ci-stabilisation-20261109` | `4022bcd2d1` | #50 | INTEGRATION_REQUIRED | 0 | 0 |
| `audit/day1-dedicated-security-ci-20261109` | `9c37ea55d6` | #52 | INTEGRATION_REQUIRED | 0 | 0 |
| `audit/post-merge-enforcement-20261109` | `71577ed8dc` | #27 | INTEGRATION_REQUIRED | 0 | 0 |
| `development/global-foundation-v0.12` | `435f9032b9` | #12 | INTEGRATION_REQUIRED | 0 | 0 |
| `docs/tradingagents-research-roadmap` | `2fa5b8b13b` | #5 | ALREADY_INTEGRATED | 0 | 0 |
| `feature/diagnostics-integration` | `9230779b55` | #7 | ALREADY_INTEGRATED | 0 | 0 |
| `feature/evidence-risk-foundation-20261105` | `1440ec07f0` | #6 | ALREADY_INTEGRATED | 0 | 0 |
| `feature/multiyear-evidence-20261105` | `20a4470607` | — | ALREADY_INTEGRATED | 0 | 0 |
| `feature/three-market-research` | `d49b8acbf3` | #3 | ALREADY_INTEGRATED | 0 | 0 |
| `feature/walk-forward-validation` | `a8f05e2497` | #4 | ALREADY_INTEGRATED | 0 | 0 |
| `fix/binance-close-time-metadata-20261105` | `33691dbcab` | #8 | ALREADY_INTEGRATED | 0 | 0 |
| `fix/day1-breakout-decimal-assertion-20261109` | `b877d92c3f` | #51 | INTEGRATION_REQUIRED | 0 | 4 |
| `fix/paper-quotes-unittest-ci-20261112` | `09f9c9870d` | #99 | SUPERSEDED | 0 | 1 |
| `fix/ruff-legacy-baseline-20261112` | `a903ca6b3c` | #100 | REPAIR_REQUIRED | 1 | 0 |
| `integration/phase1-accounting-clean-20261108` | `8f79aa79db` | #18 | ALREADY_INTEGRATED | 0 | 0 |
| `integration/phase1-data-gates-clean-20261108` | `32e4142b9f` | #19 | ALREADY_INTEGRATED | 0 | 0 |
| `integration/phase1-pr15-review-20261108` | `faa52e80df` | #17 | INTEGRATION_REQUIRED | 0 | 8 |
| `main` | `b973e43308` | — | ALREADY_INTEGRATED | 0 | 0 |
| `repair/restore-v06-source-20261103` | `15caf4fae9` | — | HISTORICAL_RETAIN | 2 | 0 |
| `research/archival-pit-evidence-20261108` | `d0cdcc3448` | #20 | ALREADY_INTEGRATED | 0 | 0 |
| `research/archive-byte-integrity-20261108` | `6739d937b4` | #21 | ALREADY_INTEGRATED | 0 | 0 |
| `research/archive-provenance-phase2-20261108` | `5b48366ae4` | #22 | ALREADY_INTEGRATED | 0 | 0 |
| `research/auth0-discovery-pkce-main-20261110` | `faf51b983d` | #86 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/auth0-jwt-paper-staging-20261109` | `fbdb0e2776` | #58 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/auth0-oidc-browser-staging-20261109` | `ea04a61708` | #60 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/auth0-oidc-session-foundation-20261109` | `6d13cd25fa` | #59 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/auth0-staging-integration-audit-20261109` | `8933e740b4` | #57 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/auth-ownership-revocation-20261111` | `cf367d371a` | #93 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/authenticated-entry-audit-20261110` | `9a33d1513d` | #83 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/authenticated-readonly-dashboard-api-20261110` | `529c21baf9` | #76 | REPAIR_REQUIRED | 2 | 2 |
| `research/authenticated-readonly-pg-staging-20261109` | `d72c20f852` | #74 | INTEGRATION_REQUIRED | 0 | 1 |
| `research/authenticated-staging-composition-20261110` | `9849a4c71a` | #81 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/authenticated-staging-entry-integration-20261110` | `4eafca676d` | #84 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/behaviour-simulation-prototype` | `5c23f9c386` | #14 | HISTORICAL_RETAIN | 0 | 0 |
| `research/chatgpt-engineering-team-20261112` | `9c07887320` | #91 | ALREADY_INTEGRATED | 0 | 0 |
| `research/ci-evidence-coverage-20261111` | `6f5250b82a` | #92 | SUPERSEDED | 0 | 0 |
| `research/ci-legacy-repair-20261112` | `0c0a99f62f` | #103 | READY_FOR_REVIEW | 0 | 0 |
| `research/ci-security-baseline-20261112` | `194a4a340b` | #97 | READY_FOR_REVIEW | 0 | 0 |
| `research/combined-evidence-regression-20261108` | `fd8fff9bbe` | #25 | ALREADY_INTEGRATED | 0 | 0 |
| `research/consolidated-assurance-review-20261109` | `757cd7c8c1` | #33 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/daily-session-import-20261109` | `8ee1030554` | #53 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/day2-independent-accounting-oracles-20261109` | `bcf314e4e5` | #54 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/end-to-end-promotion-enforcement-audit-20261109` | `fc53492338` | #26 | ALREADY_INTEGRATED | 0 | 0 |
| `research/eodhd-disabled-adapter-20261109` | `b83ba23ed2` | #47 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/external-bff-wsgi-20261110` | `ddafb88ca0` | #78 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/integrity-gates-20261107` | `63a73ff0af` | #11 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/issue16-accounting-edgecases-20261109` | `2f00603f6c` | #45 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/issue16-fill-identity-fee-guard-20261109` | `677b53cdd6` | #46 | ALREADY_INTEGRATED | 0 | 0 |
| `research/issue16-independent-accounting-oracle-20261109` | `7b393a5e29` | #44 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/issue16-main-integration-20261109` | `126b155f7e` | #38 | ALREADY_INTEGRATED | 0 | 0 |
| `research/issue16-main-reconciled-ci-20261109` | `63fb0463c5` | #43 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/issue16-phase1-adversarial-verification-20261109` | `311ed87963` | #37 | INTEGRATION_REQUIRED | 0 | 8 |
| `research/issue16-reconciliation-review-20261109` | `1c100669b6` | #36 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/live-paper-console-20261112` | `f9eff55b99` | #101 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/live-paper-market-data-foundation-20261112` | `5b893b6e34` | #98 | ALREADY_INTEGRATED | 0 | 0 |
| `research/minimal-auth-boundaries-main-20261110` | `b4eac82018` | #85 | ALREADY_INTEGRATED | 0 | 0 |
| `research/multi-asset-v0.11` | `f388d9c957` | — | HISTORICAL_RETAIN | 0 | 0 |
| `research/oidc-account-provisioning-20261109` | `ccd1eef694` | #65 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/oidc-ownership-api-gate-20261109` | `1e49e2dfe5` | #66 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/oidc-postgres-security-foundation-20261109` | `8aaebfd9bf` | #68 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/oidc-proxy-host-security-20261109` | `45abbabee5` | #64 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/oidc-readonly-rate-limit-20261109` | `ebe8141f17` | #67 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/oidc-session-paper-isolation-20261109` | `e4512e7a0b` | #61 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/oidc-shared-session-postgres-20261109` | `7b63fda59a` | #62 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/oidc-transport-hardening-20261109` | `b2a9cef8e6` | #63 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/opaque-session-foundation-main-20261110` | `1edfae3e5a` | #87 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/paper-first-copy-trading-gates-20261109` | `251d8451d4` | #56 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/paper-risk-failclosed-20261109` | `7130307c0d` | #42 | REPAIR_REQUIRED | 2 | 2 |
| `research/paper-runtime-hardening-20261109` | `fa3c07018f` | #41 | INTEGRATION_REQUIRED | 0 | 2 |
| `research/paper-runtime-integration-20261109` | `567fe3b2c7` | #40 | INTEGRATION_REQUIRED | 0 | 2 |
| `research/paper-simulator-foundation-20261109` | `b718179861` | #39 | ALREADY_INTEGRATED | 0 | 0 |
| `research/per-account-db-role-isolation-20261110` | `3151ce621e` | #80 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/personal-edition-paper-verification-20261111` | `af3efaafb0` | #89 | INTEGRATION_REQUIRED | 0 | 1 |
| `research/personal-edition-phase0-20261111` | `e5c215f89d` | #88 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/phase1-evidence-engine-20261108` | `c5d0aabf78` | — | HISTORICAL_RETAIN | 0 | 5 |
| `research/phase1-integrated-audit-20261108` | `30ce4530ca` | — | HISTORICAL_RETAIN | 0 | 7 |
| `research/phase2-combined-integration-20261109` | `4a1d3ae2bf` | #34 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/phase2-crypto-no-skips-ci-20261109` | `51b8863fed` | #35 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/phase2-independent-enforcement-verification-20261109` | `444cc2a050` | #28 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/phase2-three-gates-20261109` | `188f6ed6b4` | #29 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/phase3-shared-limiter-20261112` | `6c5513711f` | #96 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/phase3-tenant-role-isolation-20261112` | `2f94e82368` | #95 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/postgres-adversarial-isolation-20261109` | `c35dfa00c7` | #70 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/postgres-real-integration-ci-20261109` | `22fd165e91` | #69 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/postgres-rls-transaction-hardening-20261110` | `b161da0323` | #79 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/postgres-staging-release-gates-20261109` | `e90f68f836` | #71 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/pr76-ci-oidc-bff-hardening-20261110` | `f266f58694` | #77 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/pr92-independent-hardening-20261111` | `6839abe3bd` | #94 | READY_FOR_REVIEW | 0 | 0 |
| `research/promotion-bypass-audit-20261108` | `d8ad0885b8` | #24 | ALREADY_INTEGRATED | 0 | 0 |
| `research/provenance-evidence-gate-20261108` | `8f6b350b3e` | #23 | ALREADY_INTEGRATED | 0 | 0 |
| `research/provider-neutral-foundation-20261109` | `41cda73050` | #48 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/proxy-peer-trust-verification-20261109` | `74225322e8` | #72 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/regime-robustness-review-20261111` | `207319429f` | #90 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/render-safe-staging-entry-20261109` | `0c129c6f09` | #73 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/security-main-reconciliation-20261112` | `f41e8c7ee4` | #104 | READY_FOR_REVIEW | 0 | 0 |
| `research/session-pit-validation-20261109` | `dc98bf7e07` | #49 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/staging-acceptance-audit-20261110` | `90489faaef` | #82 | INTEGRATION_REQUIRED | 0 | 3 |
| `research/step1-security-entrypoint-audit-20261109` | `61b208e8b7` | #30 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/step2-archive-trust-boundary-20261109` | `ff2d05371c` | #31 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/step3-nav-cost-independent-verification-20261109` | `8b870ff060` | #32 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/strategy-evidence-gates-v1` | `979a305d84` | #15 | INTEGRATION_REQUIRED | 0 | 4 |
| `research/strategy-v0.8` | `6f7b893ee4` | #9 | HISTORICAL_RETAIN | 0 | 0 |
| `research/strategy-v0.9` | `40f0c34d43` | #10 | HISTORICAL_RETAIN | 0 | 0 |
| `research/tradingagents-071-causal-accounting-audit-20261110` | `de370d0bed` | #75 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/tradingagents-075-cost-input-hardening-20261112` | `8864330024` | #102 | INTEGRATION_REQUIRED | 0 | 0 |
| `research/week3-preregistered-strategy-discovery` | `2dfd3a9dc0` | — | HISTORICAL_RETAIN | 0 | 4 |
| `research/xtrend-screenshot-evidence-20261109` | `f5840aa587` | #55 | INTEGRATION_REQUIRED | 0 | 0 |
| `restore-v0.6-source` | `5421ce0422` | — | HISTORICAL_RETAIN | 2 | 0 |
| `restore-v06-20261103` | `8b41a40b8b` | #1 | ALREADY_INTEGRATED | 0 | 0 |

## Limits

- Inventory and CI are timestamped snapshots; later branch updates require recollection at their new exact SHAs.
- Original branch creation tips require unavailable reflogs/audit provenance and are not fabricated.
- Ancestry/content equivalence is not independent security approval.
- Historical branches are retained; no branches/PRs are deleted, closed or merged.
- Reserved prospective data is never read; protected paths block content merging.
