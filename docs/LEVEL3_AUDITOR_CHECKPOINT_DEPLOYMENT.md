# Auditor-controlled checkpoint deployment contract

## Implemented in repository

`tools/level3_staging/auditor_checkpoint.py` verifies the entire PostgreSQL audit chain using `verify_audit_chain`, rejects empty chains, compares the previous independently trusted head against the historical row to detect rewrites, requests an Ed25519 signature from an injected signer, checks it against a pinned auditor public key, uses a content-addressed create-only storage key, downloads the stored record, compares exact bytes and verifies the downloaded signature. Tests include signature mismatch, duplicate height, readback corruption and non-ancestor denial.

## Required operational isolation (NOT yet provisioned)

1. Create an auditor-owned persistent Ed25519 key in a KMS/HSM under a **different account and operator identity** from the broker and Neon. Disable key export, rotation without signed transition and broker permissions to sign. Pin the public key fingerprint out-of-band.
2. Implement a signer adapter whose `sign(bytes)` calls the auditor KMS. Never load a private key into the broker process, GitHub Actions or repository.
3. Implement an auditor-only storage adapter with `create_once(key, bytes)` and `read(key)`, enforce object retention/immutability and no overwrite/delete by broker. Maintain a separate trusted latest-head pointer with atomic compare-and-swap, and prevent competing auditors from advancing from stale checkpoints.
4. On every checkpoint, load the **previous trusted** receipt from independent storage, validate its signature and audience, verify the complete PostgreSQL chain and ancestry at the previous sequence, then sign and create the new object. Only acknowledge after independent readback and atomic latest-head advancement. An ambiguous write requires manual reconciliation.
5. Verify with two distinct identities that the broker cannot read signing material, invoke the signing API or mutate the external checkpoint store; auditor can sign and append but cannot change an existing retained object.
6. Capture real audit events, demonstrate two monotonic checkpoints and reject rollback, same-height equivocation, corruption, concurrent writers and key substitution. Record timestamped logs and independently inspect KMS and storage audit logs.

## Current limitation

The module is an auditor-side **protocol library**, not a deployed independently controlled signing service or durable append-only checkpoint store. The provided `store` abstraction does not itself guarantee immutability, and the current function does not atomically manage a latest-head pointer. Existing staging audit table was empty at last inspection. Consequently `independent_signing_key`, `external_monotonic_checkpoint` and `full_chain_verification` remain **NO-GO** until the above deployment and live acceptance evidence exists. Do not enable production or live trading.
