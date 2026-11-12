# Alpha Labs isolated private staging — release gate (2026-11-12)

Status: NOT DEPLOYED. Research-only preparation; no broker trading.

## Verified inventory
Render workspace: tea-dbloi19srm7s73f93bgg (Shannon's workspace).
Existing health-probe web service: srv-dbop6f3bc2fs73cqfksg, branch research/render-safe-staging-entry-20261109; auto-deploy off; publicly routable 0.0.0.0/0. Do not repurpose or deploy this service until ingress review.
Existing staging PostgreSQL: dpg-dboq4j7f3r2c73bvlif0-a, PostgreSQL 16, Singapore, free plan, expiry 2026-12-09. Do not use as durable journal/checkpoint storage without protected backup/restore and lifecycle decision.
Q3HASH services are unrelated and MUST NOT be changed.

## Release candidate
Source: research/master-integration-20261112 (PR #105), dependent on #104 and #103. Pin an immutable accepted commit SHA at deployment time; never use the legacy deployment/render-paper-staging.yaml branch research/paper-first-copy-trading-gates-20261109 as the current release source.

## Security prerequisites (all mandatory)
- Independently review #103 CI/dependency changes and disposition Bandit B310 findings; review B104 wildcard bind in health probe. No silent suppression.
- Review #104 OIDC verifier, session revocation, owner provisioning, PostgreSQL RLS and shared quotas; require current-head CI and adversarial tests.
- Review #105 journal/checkpoint, exactly-once order IDs, risk HALT, watchdog, and recovery; require current-head CI.
- Configure a separate Auth0 staging application with exact HTTPS callback/origin, issuer/audience, PKCE, verified JWKS, durable opaque sessions and logout/revocation. No credentials in repository.
- Use isolated staging secrets from Render secret configuration; never reuse production credentials. Keep broker/exchange execution keys absent.
- Verify trusted proxy socket peer, HTTPS canonicalisation, cookies, CSRF and rate limits. No unrestricted public order API.
- Provide private single-writer persistent journal mount with restrictive permissions and an independently protected checkpoint/key/backup channel; prove backup restore and crash recovery.
- Verify account/tenant denial, signed-out/wrong-owner denial, forged headers, duplicate orders, stale feeds, emergency HALT and process restart.
- Verify physical Android browser login, sign-out, stale-data, outage, recovery and accessibility flows.
- Manual deployment only after independent acceptance and explicit release approval. Live trading always disabled.

## Rollback
Keep existing service and database unchanged. If an isolated service is later provisioned, disable its ingress and roll back to the pinned previous image/commit; retain evidence and protected backups.

## Decision
Private staging: NO-GO pending above controls. Public paper and live execution: NO-GO.
