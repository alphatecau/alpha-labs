# Level 3 PostgreSQL login-role verification — 2026-11-19 AEST

## Dedicated Neon staging
Project `frosty-river-38771873`, branch `br-solitary-hall-a7h0lefq`, database `level3custody`.

Created **two password-authenticated LOGIN roles** through Neon with scoped `read_only` access to `level3_custody`; generated credentials were not printed into the engineering record:
- `level3_broker_login` — member of `level3_broker`
- `level3_auditor_login` — member of `level3_auditor`

Each role has `NOSUPERUSER`, `NOCREATEROLE`, `NOBYPASSRLS`, a `statement_timeout=5s` setting and a connection limit (broker 3, auditor 2).

## Live effective privilege checks
| Permission | Broker login | Auditor login |
| --- | --- | --- |
| remote_nonce INSERT | yes | no |
| approval_claim INSERT | yes | no |
| approval_claim UPDATE | yes | no |
| approval_claim DELETE | no | no |
| audit_event INSERT | yes | no |
| audit_event UPDATE | no | no |
| audit_event DELETE | no | no |
| audit_event TRUNCATE | no | no |
| audit_event sequence USAGE | yes | no |

All checks were made using `pg_roles`, `pg_has_role`, `has_table_privilege` and `has_sequence_privilege` from the owner connection.

## Critical qualifications
- Effective ACLs were checked by role name, not by authenticating as each login identity.
- Neon-generated passwords are **not** stored in this repository; separate secure credential delivery into Render is required.
- Role-level defaults do not replace application-side `SET LOCAL statement_timeout` and TLS verification.
- Existing read-only grant means broker can SELECT custody tables. Consider narrowing broker SELECT on audit history after independent chain anchoring is implemented.
- Approval UPDATE currently allows any matching row at the SQL privilege layer; application must enforce conditional transition, with DB-level protections considered before enabling writes.
- Audit hash head is not anchored outside Neon. No cloud write endpoint is enabled.

## Release gate
**NO-GO** until authenticated connection tests, ephemeral PostgreSQL CI, crash-injection recovery, independent anchor, and physical Android acceptance pass.
