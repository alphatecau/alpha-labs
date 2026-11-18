# Level 3 Google Drive custody integration — staged, not enabled

Status: **NO-GO for remote writes**. Google Drive folders have been created and the separate-account folder is visible to the primary account, but no broker-to-Drive upload or independent auditor signing workflow has passed acceptance.

## Verified folder inventory (19 November 2026)

| Trust boundary | Purpose | Google Drive folder ID |
|---|---|---|
| Primary account | Custody root | `1UiJfDAIVXh7YvPF9YHXP36uci1Ee5680` |
| Primary account | Durable file copies | `1MwkEMJIfpoxnzZ9OzcYzTM4q2IIZ0ka7` |
| Primary account | Recovery evidence | `1Eg0Z7NIofV6_0HiH2Gw4U5i4iTE9wWaa` |
| Primary account | Non-authoritative audit staging | `1MwE4aXeDHBFEeY4o4oqrgv2TBTcWED4D` |
| Separate auditor account | Independent audit folder | `118pwq_VOAGeeS1NOTXmoA4ZVEx4AcMo6` |

The primary connector can read metadata for the separate auditor folder but reports `current_user_can_share=false`. The provider did not return an authoritative permissions list or owner identity. **Do not treat folder visibility as proof of ownership, read-only access, retention, immutability, or write permissions.**

## Separation of duties

1. The broker must never receive the auditor account's OAuth refresh token, Ed25519 signing private key, or write access to the auditor's folder.
2. The broker may upload encrypted, content-addressed file copies to a private primary-account folder **only after** a service-controlled authorization gate, conditional-create semantics, integrity readback and crash-replay tests pass. Drive's ordinary upload API does not itself provide a reliable immutable create-if-absent guarantee.
3. An independent auditor reads the canonical Neon audit head and independently verifies the complete chain, verifies durable object digests, signs a canonical receipt with an offline/private auditor key, and uploads the signed receipt using the auditor account.
4. A separately trusted checkpoint (e.g., retained off-broker signed digest and monotonic sequence) is required to detect rollback, deletion, equivocation and omission. A signature without a retained checkpoint is not independent immutability.
5. Fail closed when the auditor is unavailable, permissions drift, an upload is ambiguous, a readback digest differs, or a checkpoint cannot be verified. Never fall back to the Render filesystem as authoritative storage.

## Receipt acceptance

- Use the existing `external_anchor.verify_anchor` for Ed25519 signature verification and exact custody-head match.
- Use `anchor_continuity.verify_continuity` to reject rollback and same-height equivocation. When the head advances, independently verify ancestry using the complete ordered Neon audit chain; the continuity helper alone cannot prove ancestry.
- Record Drive file ID, account identity, expected SHA-256, readback SHA-256, receipt sequence, timestamp and independent trusted checkpoint digest in evidence.
- Do not store bearer tokens, credentials, customer secrets, raw personal data, or unencrypted broker payloads in this repository.

## Acceptance still outstanding

- Separate auditor account connected and authenticated for **auditor-owned writes**.
- Exact folder ownership/permissions verified under the auditor account, and public/domain sharing denied.
- Independent auditor key provisioned outside broker/Render/Neon; signing and key-rotation tested.
- Upload/readback/conditional-create and interrupted-upload recovery verified with disposable test objects.
- Signed checkpoint verified against complete Neon audit chain and a separately retained trusted checkpoint.
- Render-to-Neon TLS authentication, physical Android acceptance, security review and release approval.

Keep PR #182 draft and `LEVEL3_CUSTODY_MODE=disabled` until these gates pass.
