# Alpha Labs Personal Edition — Phase 0 migration assessment (2026-11-11)

Status: research-only planning artifact. No deployment, migration, credential change, broker connection, live order, or trading authorisation.

## Verified baseline
- Repository: alphatecau/alpha-labs; default branch main; assessed commit cd9448fadda872873e394848c7f457d77e10efe5.
- Existing offline paper runtime: packages/alpha_lab/src/alpha_lab/research/paper_runtime.py. Its module explicitly declares no HTTP server, broker, external orders, scheduler or credentials; it replays an integrity-checked journal and halts on recovery, timestamp, quote freshness, risk or operator approval failure.
- Existing research modules include paper_simulator.py, paper_risk.py and paper_journal.py; tests include tests/unit/test_paper_simulator.py.
- Main README describes mobile operator UI under apps/sites, offline research foundation under packages/alpha_lab, and backend/dashboard/worker as planned. Existing GPT Site must remain unchanged.
- Main contains minimal OIDC verification and trusted proxy primitives from merged PR #85; these are not a complete accepted owner-login/session deployment.
- Open research PRs include #86 Auth0 discovery/PKCE, #87 opaque PostgreSQL sessions, #84 staging WSGI entry, #79 disposable RLS fixture, #78 external BFF, #76 read-only research API, #75 accounting safeguards and #74 authenticated staging composition. Their presence does not imply approval, integration or passing latest-head CI.
- GitHub connector returned no pull-request-triggered workflow runs or combined statuses for the assessed main SHA. This is insufficient to declare CI passed or failed.

## Migration decision
Target: private single-owner research and paper-trading service. Preserve independent risk controls, verified identity, auditability, data provenance and future ability to separate execution from research. Do not remove security gates merely because the product has one user.

### Reuse
- Offline research and provenance/validation.
- Paper runtime, simulator, journal and deterministic risk policy, after focused tests.
- Existing mobile UI as a design reference, without modifying the GPT Site.
- Reviewed OIDC/proxy primitives and future external BFF after real browser and trusted ingress verification.

### Defer
- Customer onboarding, subscription billing, multi-tenant provisioning and global broker marketplace.
- Live broker adapter, signing, live orders and copy trading.
- Autonomous agent execution; agents produce research only.

### Architecture
Owner browser -> HTTPS external dashboard/BFF -> verified owner session -> read-only research API -> research store.
Separately: validated market data -> deterministic research and AI analysis -> independent risk decision -> offline simulated ledger/journal -> reconciled read-only dashboard outputs.
No direct path from AI agents, browser or GPT Site to broker execution. Live adapter absent/disabled.

## Ordered implementation gates
P0-A: Confirm latest main and PR heads; collect actual CI job results; establish test baseline.
P0-B: Map exact paper ledger/risk/journal interfaces and independently reconcile cash, NAV, fills, fees and restart behavior.
P1: Implement owner allowlist based on immutable issuer+subject, confidential OIDC PKCE callback, persistent one-use state and revocable server-side session; adversarial browser tests.
P1: Verify actual Render ingress socket-peer trust and isolated database least privilege; independent security review.
P2: Build separate authenticated personal dashboard and read-only BFF; retain existing GPT Site untouched.
P3: Connect simulated-only execution, idempotency, provenance, monitoring and HALT; run forward paper tests.
P4: Add bounded agent committee with no order authority.
P5: Independently review security, strategy robustness, legal/broker eligibility and operations before any separate live-capital authorisation.

## Acceptance and explicit limitations
- Never assert profitable strategy: existing research rejected candidate edges.
- Preserve reserved 2027-01-01 to 2028-01-01 UTC evaluation window.
- Proposed risk defaults: 0.25% planned per position, 1% aggregate planned stop risk, 2% daily loss suspension, 5% drawdown suspension, 1x initial leverage. Confirm enforcement in tests; planned loss is not a guaranteed maximum.
- No automated live trading; no deployment or merge authority.
- This document is not evidence that tests have been executed or external infrastructure accepted.
