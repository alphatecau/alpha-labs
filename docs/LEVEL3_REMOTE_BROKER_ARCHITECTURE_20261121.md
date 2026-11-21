# Level 3 remote broker architecture decision (development only)

**Status: NOT APPROVED FOR ACTIVATION.** Existing Render `alpha-labs-level3-broker-probe` is a public HTTPS read-only probe on the free plan. Its `/readyz` intentionally returns HTTP 503. Do not repurpose it into a write service.

## Critical constraint

The Android worker and a Render service cannot share the current local Unix socket. Render cannot directly create files in Termux's local filesystem. A remote broker must therefore authorise a precisely bound operation, while a local constrained worker applies it **only after verifying an independently signed authorisation**. This changes the current broker architecture and requires a new threat model. Do not tunnel a raw remote file-write endpoint to Termux.

## Proposed protocol, subject to review

1. Termux worker creates a request for a create-only path matching `signed_create.ALLOW`, content SHA-256, unique random nonce, expiry, and local workspace identity. No shell commands, overwrites, Git operations, trading or generic filesystem access.
2. Authenticated broker receives the request via TLS, verifies device identity, rate limits, operator intent, expiry and digest, and durably records the nonce and decision. No signing private key in worker or broker.
3. Independent operator-controlled signer signs the canonical approval. The broker returns approval and signature; it never receives arbitrary write authority to the phone.
4. Local worker verifies the signer public key, exact path, SHA-256, nonce, expiry and staging root, then performs an atomic create-only operation with symlink protection.
5. Worker emits a signed receipt. Broker durably records receipt and reconciles its independent audit anchor. Missing acknowledgements, storage errors, conflicting nonces, stale approvals or mismatched hashes fail closed. Recovery must not retry an ambiguous create without reconciliation.
6. Independently signed readiness must prove current broker identity, signer custody, durable storage, audit anchor, connector authentication and tested Android identity separation. A simple HTTPS `{"ready":true}` response is never sufficient.

## Infrastructure constraints

- The existing Render free web service has no durable filesystem custody guarantee. Do not store authoritative nonces, audit anchors or signer keys in its ephemeral storage.
- Existing free Render PostgreSQL staging database expires 2026-12-09 according to the Render inventory. Do not rely on it for permanent audit retention or irreversible write authorisation.
- Existing services currently allow public ingress. Do not expose approval endpoints until authenticated transport and strict service identity are independently tested.
- Keep Level 2 tunnel running and the Level 3 Render probe read-only; no production deployment or new paid resources.

## Required gates before activation

- Review threat model including compromised Termux UID, broker compromise, replay, audit rollback, signer compromise, MITM, connector abuse and network partitions.
- Establish independent signer and durable append-only audit anchor; document cost and retention before provisioning.
- Implement authenticated device-to-broker transport with certificate validation and strict request size/time bounds.
- Independent tests: duplicate/replay, concurrent nonces, digest/path mismatch, redirect and credential leakage, clock skew, stale readiness, crash between create and receipt, journal rollback, worker/broker compromise, offline broker, and device recovery.
- Test on real Android and isolated staging identities; obtain explicit operator approval for activation.

The `remote_readiness.py` module is **observation-only** and never grants write authority. It is not a broker client or signed attestation verifier.
