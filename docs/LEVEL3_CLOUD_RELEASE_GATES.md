# Level 3 cloud staging acceptance and outstanding controls

Status: **NO-GO**. This document is an engineering gate, not permission to enable writes.

## Verified in GitHub Actions

Workflow run 44357762383 on repair branch:
- `offline-test`: success.
- `postgres-integration`: success against disposable PostgreSQL 18 container (`level3_ci_test`).

These results do **not** demonstrate password-authenticated Neon staging roles, Render-to-Neon connectivity, independently durable file custody, external audit anchoring, or physical Android acceptance.

## Blocking security issues

1. **Caller-controlled assertions:** `signed_broker_pipeline.signed_create` accepts `durable_storage`, `independent_anchor`, and `operator_approved` as booleans. The environment gate is additional protection, **not proof** that these controls exist. Do not enable `LEVEL3_CUSTODY_MODE` until each assertion is derived from server-controlled, verified state and approval evidence.
2. **Ephemeral file custody:** `intent_recovery.reconcile_intent` uses a local filesystem. Render free instance storage is ephemeral; it cannot be the authoritative destination. Implement durable private storage with immutable object keys, conditional create, digest verification, and durable replay reconciliation.
3. **Filesystem race:** path validation followed by filesystem access is not sufficient against concurrent symlink swaps. Use directory-descriptor-relative, no-follow operations or replace the local file writer with a verified object-store implementation.
4. **External anchor:** `external_anchor.verify_anchor` validates a signature, but does not create or persist an independent immutable anchor. The auditor's signing key and anchor store must remain outside broker and Neon write permissions.
5. **No authenticated write HTTP API:** Render's deployed probe intentionally returns 405 for POST and 503 for readiness. Do not expose write operations before completing the above controls.
6. **Role and deployment acceptance:** Validate dedicated broker/auditor PostgreSQL logins over TLS, explicit grants and denied operations, isolated tenant boundaries, network restrictions, secret rotation, and restart recovery.

## Required end-to-end release evidence

- Signed request accepted exactly once for an approved allowlisted path and matching digest; replays, expired signatures, wrong audiences, unknown keys, malformed payloads and unapproved requests denied without side effects.
- Simulated crashes at every claim/write/audit boundary recover exactly once with independently durable bytes and consistent audit evidence.
- A malicious or compromised broker cannot alter, delete, forge, or silently roll back independently stored audit heads.
- Staging Render service authenticates to Neon with its least-privilege broker login; auditor login remains unavailable to Render.
- Android 15 operator test confirms approved workflow, denial workflow, reconnection and restart.
- CI at final PR head passes, independent review resolves security findings, and explicit release authorisation is recorded.

## Preserve current controls

Keep `LEVEL3_CUSTODY_MODE=disabled`; Render read-only probe only; no public write API, no live trading, no merge of draft PR #182 until acceptance evidence is complete. Maintain existing Level 2 Android/Termux gateway.
