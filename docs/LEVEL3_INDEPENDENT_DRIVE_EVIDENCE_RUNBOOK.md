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
