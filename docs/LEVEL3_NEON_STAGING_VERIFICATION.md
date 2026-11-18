# Level 3 Neon staging verification — 2026-11-18 UTC

## Provisioned (verified via connected Neon API)
- Organisation: `org-wispy-water-75232654`, plan `free`
- Dedicated project: `frosty-river-38771873` (`alpha-labs-level3-custody-staging`)
- Region: `aws-ap-southeast-2`; PostgreSQL 18
- Database: `level3custody`; owner: `level3_owner`
- Three schema tables created successfully: `remote_nonce`, `approval_claim`, `audit_event`
- Role definitions: `level3_broker NOLOGIN` and `level3_auditor NOLOGIN`; broker has DML grants, auditor has SELECT-only grants.
- Live SQL duplicate nonce constraint handled as expected; test row removed. All three tables verified empty.

## Limitations / blockers
- NOLOGIN roles are not credentials for a running service. Authentication, connection provisioning, role grants and actual isolation tests remain pending.
- Broker currently has UPDATE permission on approval rows. Least-privilege must be tightened with narrowly scoped functions or row controls before deployment.
- The audit table and hash-chain are **not** independently anchored; database owner can still modify/delete audit data.
- Neon free compute and storage have limits. Avoid sustained polling and never assume paid resources are authorised.
- No Render database connection configured. No secrets copied into GitHub or chat.
- No end-to-end Android → cloud → database → allowlisted write tests performed.
- Level 2 gateway remains out of scope. Render probe remains read-only.

## Gate
**NO-GO** for public write endpoint, PR merge or production activation.
