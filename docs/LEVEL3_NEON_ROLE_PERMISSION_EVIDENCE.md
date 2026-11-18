# Level 3 database role-permission evidence — 2026-11-18 UTC

## Live checks
Connected to dedicated Neon project `frosty-river-38771873`, database `level3custody`, as `level3_owner`.

Read `pg_roles`: `level3_auditor` and `level3_broker` are NOLOGIN, NOSUPERUSER, NOCREATEROLE.

Read `has_table_privilege` against both roles:
| Role | Nonce SELECT | Nonce INSERT | Audit SELECT | Audit INSERT | Audit UPDATE | Audit DELETE |
| --- | --- | --- | --- | --- | --- | --- |
| level3_auditor | true | false | true | false | false | false |
| level3_broker | true | true | true | true | false | false |

Attempted `SET LOCAL ROLE level3_auditor` from `level3_owner`: permission denied (SQLSTATE 42501). Therefore these checks establish role definitions and ACLs, **not** successful authenticated logins or complete runtime tenant isolation.

## Outstanding
1. Dedicated broker login identity, securely managed credential, role membership and real credential-based deny tests.
2. Audit anchoring independent of database owner.
3. Transactional coupling of nonce claim, approval, audit event and file operation; crash-recovery tests.
4. End-to-end Android → authenticated gateway → isolated broker → PostgreSQL staging.
5. Keep Render probe read-only and Level 2 unchanged until gates pass.

No passwords or connection strings are stored here.
