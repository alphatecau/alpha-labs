# Level 3 consolidated engineering acceptance status

## Implemented
- Isolated Neon project `frosty-river-38771873`, free organisation, PostgreSQL 18.
- Custody tables and NOLOGIN broker/auditor roles; verified role ACLs using `has_table_privilege`.
- Verified basic SQL rollback and duplicate nonce uniqueness; test tables empty after live checks.
- Offline Ed25519 remote auth, replay ledger, custody claim/complete, audit append and chain verification.
- New GitHub Actions `postgres-integration` job runs against a disposable PostgreSQL 16 service with `level3_ci_test` database. Test refuses any other database name.
- Integration tests cover replay, claim rollback on conflicting approval, completion once and audit verification.

## Not verified
- New integration workflow success; await GitHub Actions completion.
- SQL tests against Neon using a restricted login role (the defined roles are NOLOGIN).
- A real authenticated Render-to-Neon channel.
- Atomic audit + approval + file write under crash injection.
- External, independent immutable audit anchoring.
- Physical Android acceptance.

## Security decisions
- Existing Render service `srv-dbus2ve1egvs73ehtp50` is on **free** plan, `autoDeploy=no`, and uses read-only `deployment/level3_cloud_probe.py`.
- Render service permits public network ingress, but POST is intentionally disabled in probe. Do not enable write routes without full security acceptance.
- Never store database credentials in GitHub or chat. Never modify the Level 2 gateway.
- PR #181 remains **NO-GO** for merge/production until gates pass.

## Next integrated delivery
1. Confirm disposable PostgreSQL CI pass and fix defects.
2. Create least-privilege service login using secret-safe provisioning, test actual grants.
3. Implement server-side authenticated transport with secure credential injection.
4. Implement independently anchored receipts and crash/replay/recovery acceptance.
5. Complete physical Android E2E testing before promotion.
