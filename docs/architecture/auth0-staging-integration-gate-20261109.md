# Auth0 staging integration: verified blockers and acceptance gate (2026-11-09)

Status: **NO-GO for deployment and login**. Scope: research-only, paper status endpoint. No changes to secrets, Render, Auth0, trading or production.

## Verified repository baseline

Base: PR #56 head `e0d46861e133f54b2e369e7a7851a37a5d6b4211`.
GitHub Actions for this head report success for offline research, Sites and paper simulator workflows (runs 42582026925, 42582026966, 42582026987). These do not certify federated authentication or an operational staging deployment.

## Blocking incompatibilities (read from source)

1. `paper_identity.PaperIdentityVerifier` accepts only a bespoke **two-segment HMAC token**, whereas Auth0 access tokens for a custom API are normally signed three-segment JWTs. Never substitute the Auth0 application Client Secret for `ALPHA_PAPER_SIGNING_KEY_B64`.
2. `paper_status_wsgi.PaperStatusWSGI` explicitly requires `isinstance(verifier, PaperIdentityVerifier)`; an Auth0 JWT verifier cannot be substituted without an intentionally reviewed interface change.
3. `PaperAccountService._require` restricts subject to `[A-Za-z0-9_-]{1,64}`; Auth0 `sub` values commonly include a provider prefix and `|`. Define a stable, collision-resistant, server-derived mapping for `(iss, sub)`; never trust a browser-supplied account ID.
4. `paper_staging_app.build_app` preprovisions a single owner using `ALPHA_PAPER_OWNER_SUBJECT`. There is no authenticated self-service provisioning, role administration, revocation mechanism or multi-user registry.
5. The current Render blueprint uses `starter` plus a persistent disk and points at the earlier PR #56 branch. It is **not** an Auth0 deployment configuration; verify pricing and actual available plan before creating a service.
6. The only HTTP route is GET `/api/research/paper/status`; there are no login, OAuth callback or logout routes. A Regular Web Application must have a real server-side OIDC Authorization Code flow (state, nonce, PKCE where applicable, secure session cookie) before callback URLs are registered.
7. No end-to-end tests exist for Auth0 issuer/audience/JWKS key rotation, rejected algorithms, missing/expired/future tokens, malformed claims, cross-user isolation, session termination, or revoked access.

## Required implementation (separate reviewable security PR)

- Decide the trust boundary: server-side OIDC login + secure cookie, or frontend Auth0 login with API JWT bearer verification. Do not mix approaches or invent callback paths.
- Register a dedicated Auth0 API audience and configure RS256 JWT verification using a maintained JWT library or rigorously reviewed cryptography implementation; pin issuer and audience, reject algorithm confusion and unknown `kid`, fetch JWKS with strict HTTPS/timeouts/cache and fail closed on refresh failure.
- Introduce a verified-principal interface independent of the bespoke test verifier; derive stable per-user account keys from validated issuer + subject; retain HALT as default and no order endpoints.
- Implement explicit trusted-server account provisioning, storage durability, concurrency controls and isolation. Do not treat a single-process in-memory registry as production-ready.
- Add deterministic adversarial unit tests, integration tests with locally generated RSA keys/JWKS fixtures, and separate real Auth0 staging smoke tests without committing credentials.
- Verify CSRF/session controls, rate limits, secure transport, logout, expiry and reauthentication; audit logs must redact tokens.
- Pin the reviewed deployment commit, keep auto-deploy OFF, avoid production environments, and obtain explicit staging-deploy approval after CI and independent review.

## Manual values and ownership

Auth0 tenant: `alpha-labs-dev` (exact domain suffix not yet verified).
Auth0 Regular Web Application: `Alpha Labs Staging`. Public Client ID was supplied by the operator; **do not commit secrets**.
Render: `Alpha Labs Staging` environment exists with zero services as shown by operator screenshot.
Auth0 callback/logout/origin values: **leave unchanged** until the deployed frontend/server routes and exact HTTPS origins are verified.

## Acceptance

NO-GO until tests show: invalid signatures, wrong issuer/audience, unknown key ID, token expiry, forged identity and cross-user access all rejected; authentic owner access succeeds; independent non-owner access isolated; logout and session expiry verified on Android; persistent storage and shared quotas verified; no broker/live-copy endpoints exist. A passing research CI run alone does not satisfy these gates.
