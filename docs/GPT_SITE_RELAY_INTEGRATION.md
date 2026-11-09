# Alpha Labs GPT Site integration — research-only contract

Status: **not connected or deployed**. This branch adds a prototype authenticated API and owner-scoped PostgreSQL read adapter.

## Architecture
Existing GPT Site -> trusted server-side relay (NOT browser JS) -> Render HTTPS API -> read-only PostgreSQL account. The relay verifies the site's session and maps it to the backend's immutable owner ID. Only the relay can mint HMAC-SHA256 assertions (short expiry <=120 seconds) with the signing secret kept server-side. Do not place a bearer signing secret, database DSN, or privileged token in site HTML/JavaScript.

## API
- GET /healthz — public, does not disclose user data.
- GET /api/v1/research/runs — signed relay assertion required; returns at most 50 owner-scoped registry records (run ID, SHA256 evidence reference, timestamp).
- GET /api/v1/research/summary — signed relay assertion required; returns count scope and explicitly unavailable performance until an independently verified owner-scoped performance view exists.
- POST/PUT/PATCH/DELETE — denied. No broker/trading routes.
- Missing storage, invalid assertions or backend errors fail closed.

## Critical deployment gates
1. This is a prototype; no service is deployed and the existing staging_probe.py must remain unchanged until approval.
2. Implement a trusted session-verifying site relay. GPT Sites integration capability has NOT been verified; if Sites cannot host server-side secrets, use a separate authenticated BFF and do not call this API directly from the browser.
3. Bind the app to an approved read-only database role with SELECT only, RLS or equivalent owner filtering, verified schema, and TLS/private network.
4. Wire the WSGI application to a read-only adapter through dependency injection. Default application intentionally has no data source and returns 503.
5. Use an identity provider to authenticate the end user; the relay must derive owner from the validated identity, not from browser-supplied owner IDs.
6. Add replay protection/rate limits, issuer/key rotation, monitoring, request budgets and independent security review before any public launch.
7. Never claim profitability: portfolio performance is unavailable until reconciled, reproducible owner-scoped evidence is actually present.

No merges, deploys, credentials, trading or site edits were authorised by these commits.
