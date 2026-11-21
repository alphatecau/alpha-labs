# Level 3 independent approval service — deployment decision

Decision: **prepare, do not deploy** until the approval authority and operator identity are independently verified.

## Architecture

1. Separate approval service authenticates the human operator and reviews an immutable proposal.
2. The service signs a canonical create-only grant using Ed25519. The private signing key never enters Termux, MCP, GitHub, logs, or ChatGPT.
3. The Android staging writer pins only the service public key, validates path, content SHA-256, environment, expiry and signature, then consumes the nonce in its durable replay ledger before attempting a create-only operation.
4. The writer uses exclusive creation and no-follow directory traversal. Any ambiguous crash is denied on retry and requires operator reconciliation.
5. The MCP-facing adapter can submit proposals but cannot access signing credentials, approve requests, invoke the writer directly, or alter the replay database.

## Security gates before deployment

- Verify the chosen free-tier provider's actual availability, security features and price; do not assume existing Render/Auth0 entitlements.
- Independently authenticate the operator and enforce approval in a separate security principal; do not treat an Auth0 login or GitHub review alone as a signature.
- Isolate signing key custody from MCP and Android, use secret rotation and revocation procedures, and never commit keys.
- Harden the replay ledger against same-UID tampering; SQLite alone provides durable uniqueness, **not** process isolation.
- Add signed approval issuance, authenticated review UI, short expiry, idempotent status queries, revocation and incident response.
- Verify cryptography dependency on the intended runtime; tests that skip without cryptography do not count as acceptance.
- Conduct isolated Android integration, negative security tests, recovery and rollback tests; maintain Level 2 untouched.
- Require explicit evidence of approval boundary before connecting any direct write tool.

## Current state

- Offline Ed25519 verifier and SQLite replay ledger are development components only.
- No signing authority, signing key, authenticated approval endpoint, isolated writer or connected Level 3 tunnel exists yet.
- Operator-run pinned GitHub install/update remains the accepted manual path.
