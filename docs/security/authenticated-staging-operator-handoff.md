# Alpha Labs authenticated staging — operator handoff

**Status: HOLD.** This is a preparation checklist, not an instruction to deploy.
The currently live Render service is the health-only research probe. Preserve its
branch, start command, health endpoint and Auto-Deploy=Off settings.

## 1. Evidence and scope
- Draft PR: https://github.com/alphatecau/alpha-labs/pull/74
- Verified test head before this document: 16a9938005a683d81ebcf948cede9e7b7dd0e1d3
- Four workflows passed: offline research, Sites, PostgreSQL integration and authenticated staging composition.
- No authenticated research API, database, Auth0 tenant or trading service has been deployed.

## 2. Auth0 operator configuration (requires owner)
- Create a dedicated confidential **Regular Web Application** for *staging*, not a public SPA.
- Use Authorization Code + PKCE; do not enable password or implicit grant as a workaround.
- Confirm issuer and audience/client ID match the server-side verifier.
- Set exact allowed callback URL to `https://<approved-staging-host>/auth/callback`.
- Set allowed logout/origin settings only after verifying the intended hosted origin.
- Store client secret in the Render secret manager, never in GitHub files, browser code, Sites or chat.
- Capture configuration evidence with credentials redacted.

## 3. PostgreSQL operator configuration (requires owner approval)
- Select a persistent, privately accessible PostgreSQL service and obtain approval for any charges.
- Require least-privilege roles, encrypted transport where applicable, network isolation, backup and retention review.
- Apply `postgres_security_migration.py` and `postgres_oidc_migration.py` through a reviewed one-time migration operation, not on every web request.
- Verify both migration identifiers and required tables, plus session persistence after application restart.
- Never substitute SQLite on the ephemeral free Render filesystem.

## 4. Render ingress verification (hard blocker)
- Identify the actual immediate peer address and the documented trusted-proxy topology using controlled staging evidence.
- Verify whether REMOTE_ADDR is the socket peer rather than a client-supplied forwarded address.
- Demonstrate that direct internet traffic cannot bypass the trusted proxy.
- Test Host, Forwarded, X-Forwarded-Host, X-Forwarded-Proto and spoofed REMOTE_ADDR behaviour.
- Do not use all-address CIDRs or broad private CIDRs as proof of authenticated ingress.
- If this trust model cannot be established, design an alternate authenticated ingress before deployment.

## 5. Account adapter and read-only acceptance
- Replace the in-memory/SQLite paper account adapter with a durable, tenant-isolated read-only data source, or return unavailable without disclosing another account.
- Prove issuer+subject isolation with two independent accounts, including after restart.
- Verify no account can be selected by client-supplied ID, subject or issuer.
- Verify expired/revoked sessions, OIDC state replay, cookie attributes, CSRF, rate limits, DB outages and controlled errors.
- Assert trading/order/broker/copy routes are absent or denied.
- Confirm research signals are not presented as validated profitability or executable trades.

## 6. Release decision
**DO NOT MERGE OR DEPLOY** until all gates are independently evidenced and the owner explicitly authorises a staged release. Any Auth0, database, Render or credential changes require separate approval. No live trading.
