# Level 3 custody acceptance matrix

Status: **NO-GO**. This document is a verification plan, not an assertion that cloud integration has passed.

| Gate | Evidence required | Current status |
| --- | --- | --- |
| Google Drive OAuth | API identity and read/write operations under auditor account | BLOCKED: 403 insufficient scopes |
| Independent folder | Owner email, private permissions, no broker writer access | UNVERIFIED |
| Durable primary copies | Real encrypted upload, independent download and SHA-256 comparison | UNVERIFIED |
| Upload recovery | Ambiguous response, retry, duplicate detection, delete and crash tests | OFFLINE TESTS ONLY |
| Auditor signing | Ed25519 key outside broker/Render/Neon, signature verification | UNVERIFIED |
| External checkpoint | Independently retained monotonic digest, anti-rollback | UNVERIFIED |
| Full audit chain | Independent ancestry replay and omission detection | UNVERIFIED |
| Database transport | Authenticated Render-to-Neon TLS proof | UNVERIFIED |
| Android | Physical device acceptance | UNVERIFIED |
| Release | Security review and explicit operator approval | NOT APPROVED |

## Execution rules

1. Keep `LEVEL3_CUSTODY_MODE=disabled` and remote writes disabled.
2. Keep PR #182 draft until checks pass and an independent review is complete.
3. Never put auditor refresh tokens or signing keys in Render, Neon, broker logs, or GitHub.
4. Do not treat simulated adapters, boolean gates, or a Composio 'Active' label as proof of cloud authorisation.
5. Treat Drive filenames as non-atomic; an independent create-if-absent mechanism is still required.
6. Record dated evidence for each gate, with the actor, account identity, API result and negative test.
