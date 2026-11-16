# Alpha Labs recovery roadmap — 2026-11-16

Budget: AUD $0. Production, hosted staging and live trading remain NO-GO until their separate gates pass.

1. **P0: Paper HALT race.** Review PR #135 against current main and ensure stale refreshes cannot overwrite a later failure/HALT. Require deterministic concurrency regression and independent review. Owner: security/quant reviewer.
2. **P0: Identity provisioning.** Resolve or explicitly prove mitigation of SEC-01 in `docs/security/pr122-preliminary-security-review.md`. Test untrusted caller and forged principal attempts against real entrypoints. Owner: auth/security reviewer.
3. **P1: Exact-head CI.** Trigger offline research, backend baseline, Auth0 callback, disposable PostgreSQL recovery, local paper 3.12/3.13, Ruff, Bandit and dependency audits on the review SHA. Record job URLs, tests and artifacts. Owner: CI engineer.
4. **P1: Disposable security.** Verify restricted PostgreSQL 16 login roles, FORCE RLS, tenant isolation, revoked credentials and state replay/rollback with real disposable sessions. Owner: PostgreSQL security reviewer.
5. **P1: Local paper terminal.** On clean Linux and Android/Termux, verify BTC/ETH/SOL provenance/freshness, HALT, outage, journal atomicity, SQLite crash restart, backup/restore, replay, no duplicate fills and absence of live-order adapters. Owner: quant/QA reviewer.
6. **P2: Hosted acceptance.** Only after separate authorisation and secure isolated infrastructure, execute real browser Auth0, restricted SQL, session expiry/revocation and outage recovery; obtain independent sign-off. Owner: staging operator.
7. **P3: Live capital.** Remains disabled pending independent quantitative, security, operational and regulatory acceptance and explicit separate authorisation.

## Release criteria
Local simulation: conditional GO only when exact-head safety tests pass with no unexpected skips, Android verification is recorded, the HALT race is closed and all high-severity reachable security findings are resolved or demonstrably isolated from local operation. Hosted staging: NO-GO until browser, database and independent-review gates pass. Live trading: NO-GO.

Never suppress failing checks, bypass required reviews, merge security-sensitive work without approval, or use persistent databases for destructive tests.
