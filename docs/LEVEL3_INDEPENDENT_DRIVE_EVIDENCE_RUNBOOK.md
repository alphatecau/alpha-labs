# Level 3 independent Google Drive custody — acceptance runbook

Status: **NO-GO**. This document does not authorise production or broker activation.

## Verified access (19 November 2026)

- Independent auditor identity: `alpha.tec.au869@gmail.com`.
- Auditor-owned folder: `118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6`.
- Direct Google Drive connector successfully retrieved folder metadata under the auditor account.
- Metadata showed auditor as `owner` and primary `alpha.tec.au86@gmail.com` as `reader`.
- Folder search returned no children at the time of inspection.
- The separate Composio Google Drive connection returned HTTP 403 `ACCESS_TOKEN_SCOPE_INSUFFICIENT` after browser reconnection. It is **not** an accepted upload transport.
- Direct connector metadata does not provide every field required by the offline preflight (notably `trashed` and the independent `owners` array). A successful metadata read is **not** a completed policy preflight.

## Evidence required before accepting cloud custody

1. Confirm auditor-controlled write credentials never enter the broker, Render service, repository, CI secrets, or the primary account.
2. Obtain fresh folder identity, owner, `trashed=false`, and full effective permissions through an auditor-authorised Drive API client. Fail closed if fields are unavailable.
3. Verify primary account is reader-only and no unexpected writers, groups, domain-wide or public grants exist. Check inherited permissions separately where applicable.
4. Prepare **synthetic non-sensitive** payload, record SHA-256 and exact byte count locally. Do not use customer, financial or secret data.
5. Acquire a unique PostgreSQL reservation in an isolated staging database before uploading. Do not apply migrations to production.
6. Upload the content-addressed object through an independently authenticated auditor client. Do not use a broker credential or assume the ChatGPT connector supports arbitrary binary upload.
7. Query the destination folder again: exactly one object with the expected name, parent and identity must exist.
8. Download the stored object as bytes from Drive (not a cached upload buffer). Compare SHA-256 and byte count.
9. Complete the database reservation only after verified byte readback. If upload is ambiguous, leave it reserved and investigate; do not blindly retry.
10. Independently verify the audit chain and an externally signed monotonic checkpoint with an auditor-held key. Preserve proof in an independent storage domain.
11. Verify TLS to the isolated Neon database, negative permissions, crash recovery, Android acceptance and explicit operator release approval.
12. Re-evaluate all 12 custody release gates with actual evidence. Unknown, stale or absent proof is a failure.

## Current limitations

- No confirmed binary upload/readback capability through the direct Google Drive connector in this workflow: its upload action requires an existing connector `file_uri`.
- No actual custody object has been uploaded or independently read back.
- No external signing-key custody or signed checkpoint has been attested.
- No independent Render-to-Neon TLS or physical Android acceptance evidence.
- Draft PR #182 remains unmerged; broker disabled; live trading prohibited.

## Acceptance artefacts

Retain: exact folder ID, role/permission snapshot, source payload digest and size, Drive object ID, Drive readback digest and size, reservation transaction record, audit chain head, signed checkpoint, verifier identity, timestamps, and approval decision. Never store tokens or private keys in the artefacts.


## Live read-only staging observations (19 November 2026)

- GitHub commit `897f0a4e`: all seven workflows succeeded.
- Neon project `frosty-river-38771873`, database `level3custody`, branch `br-solitary-hall-a7h0lefq`: existing schema `level3_custody` has `approval_claim`, `audit_event`, and `remote_nonce`; **`drive_upload_reservation` does not exist**. No live reservation test is possible until the separately reviewed migration is applied.
- Roles `level3_broker_login` and `level3_auditor_login` exist. Auditor has SELECT and not INSERT on those three tables; broker has SELECT and INSERT. These privilege checks do not demonstrate end-to-end tenant isolation.
- Existing three tables report `relrowsecurity=false` and zero RLS policies. A separate authorisation/isolation design review is required before release.
- The Neon connector's own SQL session reported `pg_stat_ssl.ssl=false`. This does **not** measure Render-to-Neon TLS and must not be used to pass or fail that specific gate.
- Render account exposes workspace `Shannon's workspace` (`tea-dbloi19srm7s73f93bgg`), but no workspace was selected for resource inspection. Do not infer Render staging configuration from Neon metadata.
- No cloud object was created, no production mutation was made, and no signing key was handled.

**Decision:** Release remains NO-GO. Do not set any release gate to true solely on the basis of this document.


## Render workspace verification (19 November 2026)

User explicitly authorised operations in Render workspace `Shannon's workspace` (`tea-dbloi19srm7s73f93bgg`). Read-only inventory confirmed:

- `alpha-labs-level3-broker-probe`, service `srv-dbus2ve1egvs73ehtp50`, Singapore, free plan, manual deployment, branch `research/level3-signed-staging-followup-20261118`, latest deployment `e22fe58d3eaf00b2a0b7aeb5966dbe9a61d5eca8` marked live.
- `alpha-labs`, service `srv-dbop6f3bc2fs73cqfksg`, Singapore, free plan, manual deployment, branch `research/render-safe-staging-entry-20261109`, latest deployment `0c129c6f09b9859b4464086bc97fd7f6215f9d49` marked live.
- Both services have public inbound allowlist `0.0.0.0/0`. This is network reachability, not proof that signed-write operations are exposed. Restrict network access only after confirming a viable health-check and operator access path.
- The deployed Level 3 probe source implements GET `/healthz` (200) and GET `/readyz` (503, independent custody not configured); other GET routes return 404, POST returns 405. These are **source-code expectations**, not independently verified live HTTP responses.
- No Render environment values, database credentials, or live Render-to-Neon TLS handshake were inspected. Neither staging nor production is cleared.

GitHub commit `a6ecd6fa`: seven workflows successful. Preserve auto-deploy off until evidence and operator approval are complete.


## Isolated staging migration executed (19 November 2026)

On Neon project `frosty-river-38771873`, branch `br-solitary-hall-a7h0lefq`, database `level3custody`, the additive `CREATE TABLE IF NOT EXISTS level3_custody.drive_upload_reservation` migration was applied with the same checks as `docs/LEVEL3_DRIVE_RESERVATION_STAGING.sql`, including the newer `file_id` length constraint.

Read-only post-migration queries verified: table exists, owned by `level3_owner`; 12 PostgreSQL constraints reported; both `level3_broker_login` and `level3_auditor_login` have `INSERT=false`; table contains **zero** reservation rows. No role grants or production changes were made.

**Not yet proven:** real transaction contention/recovery on this staging instance, Drive upload/download, and an authorised isolated uploader role. Keep the database table inaccessible to broker and auditor logins until a separate least-privilege uploader design is accepted. This schema migration does not pass the release gate by itself.
