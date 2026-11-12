# Auth0 PostgreSQL staging integration — implementation and approval gate

**State:** Research-only. Do not deploy, merge or enable trading.

## Implementation
- `oidc_postgres_store.py` implements hashed opaque session IDs, one-time OIDC state consumption using PostgreSQL `DELETE ... RETURNING`, revocation and expiry.
- Browser and paper-status WSGI adapters can explicitly accept this store.
- SQL schema is supplied as `SCHEMA`, **not automatically migrated**.
- Deterministic fake-connection tests cover cross-instance semantics. They are not real PostgreSQL concurrency tests.

## Required deployment dependencies (not provisioned)
1. Auth0 tenant issuer (exact HTTPS domain), confidential client ID/secret, authorised callback and logout URL, pinned JWKS and key-rotation plan.
2. A protected PostgreSQL database with TLS, least-privilege role, restricted network ingress, managed backups, migration ownership and expiry cleanup schedule.
3. A reviewed ASGI/WSGI hosting entry point, trusted proxy HTTPS handling, production-safe cookie domain and host allowlist.
4. Account provisioning and lifecycle linking verified Auth0 principals to paper-only accounts.
5. Real tenant login, callback, logout, expired-token, forged-state, non-owner, session replay, rotation and multi-worker acceptance tests.
6. Security review for CSRF, authorization, DoS/rate limits, database errors, secrets and operational audit logs.

## Verification matrix
- Unit tests and CI: see PR Actions, verify after latest commit.
- Real database integration: **NOT RUN** (no database provisioned).
- Live Auth0: **NOT RUN** (credentials/tenant configuration unavailable).
- Multi-instance isolation: **NOT RUN** (fake database only).
- Render staging: **NOT DEPLOYED**.
- Real trading: **DISABLED**.

The existing PR chain is deliberately unmerged. Explicit authorisation is required before provisioning infrastructure, secrets, or staging deployment.
