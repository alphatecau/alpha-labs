# Level 3 remote authentication — integration contract

The remote authentication implementation is currently **offline library code**; the deployed Render service is read-only and has no write endpoint.

## Proposed request flow
1. A separately authorised Android client prepares exact UTF-8 request bytes.
2. A private client key signs a canonical claim containing protocol version, POST, `/v1/signed-create`, SHA-256 body digest, `alpha-labs-level3` audience, 64-character hexadecimal nonce and expiry within 120 seconds.
3. A TLS-terminating authenticated gateway must enforce request-size and rate limits and forward **unchanged bytes** to the isolated broker.
4. The broker verifies signature and claims using `remote_auth.verify`, then claims the nonce in broker-owned durable storage using `remote_replay.claim_once`.
5. A distinct offline operator approval signature is checked by the existing signed-create implementation. A valid remote transport signature **never substitutes** for operator approval.
6. The broker writes the allowlisted staging file, reconciles its audit outbox and returns a receipt. Replay and failure remain denied.

## Mandatory pre-deployment work
- Design and test a private gateway-to-broker channel. Never publish the Unix socket or broker directly.
- Provision a durable free-tier storage backend with independent custody and protected audit anchor. The current Render free filesystem is **not approved** for this purpose.
- Provision separate identities for gateway, broker, operator signer and audit anchor; verify access restrictions in real deployment.
- Implement the HTTP adapter and exercise full end-to-end signed write/replay/restart tests against durable storage.
- Pin service identity and verify TLS, rate limiting, request framing, logging redaction and readiness attestations.
- Retain auto-deploy disabled and leave Level 2 unchanged.

**NO-GO:** Do not expose `/v1/signed-create` or enable connector tools until all gates pass.
