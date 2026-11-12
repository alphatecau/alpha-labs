# GPT Site relay and PostgreSQL security gate

## Implemented on research branch
- Trusted relay interface requires independently verified user session, derives immutable owner ID server-side, signs a short-lived owner assertion and calls only fixed read-only research endpoints.
- Fail-closed relay unit tests.
- Review-only SQL for a SELECT-only PostgreSQL role; no migration applied.

## Not yet verified / deployment blockers
1. No supported direct editor or backend-capability inspection tool for the existing ChatGPT GPT Site is available in this execution environment. Do not claim the existing Site has server-side secret storage, authentication hooks or a relay.
2. Relay is an injectable contract, not a production HTTP server. Session verification, HTTPS transport, rate limiting, replay protection, key rotation, and user identity provider integration are still required.
3. PostgreSQL role SQL is not applied or tested against Render; the read-only role does not independently enforce row-level security. A database-level RLS policy and real role permission tests are required.
4. The current staging_probe.py remains unchanged and exposes health only. Research API not deployed, and no actual user data is returned.
5. Avoid browser-side bearer signing and database credentials. If GPT Sites cannot provide a trusted server-side relay, use an independently hosted authenticated BFF and have the Site link or embed only a permitted UI integration.

## Safe next gate
Implement an OIDC verifier against the chosen issuer and JWKS, bind identity to owner records, use a dedicated HTTPS BFF, enforce PostgreSQL RLS and role isolation, then perform two-account and negative tests before deployment. No merge or trading.
