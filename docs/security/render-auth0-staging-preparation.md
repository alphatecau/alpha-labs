# Alpha Labs — Render / Auth0 staging preparation (NO DEPLOY)

## Render secrets (server-side only)

Use a **staging-only** Render environment group, attached only to the staging
research API. Define `ALPHA_TENANT_CREDENTIALS_JSON` as a secret value.
Schema (PLACEHOLDERS ONLY — never commit real values):

```json
{"schema_version":1,"accounts":{"oidc_<sha256-of-issuer-NUL-subject>":{"host":"<private-db-host>","port":5432,"dbname":"<isolated-staging-db>","user":"alpha_tenant_<id>","password":"<staging-only-secret>"}}}
```

The Render adapter reads the environment configuration and passes one account's
credential object to `TenantCredentialBroker`; the broker must be invoked only
with the verified owner from the authenticated BFF. Do not trust account headers.

**Limitations:** Render environment groups are deployment configuration, not a
dynamic vault. Changing a value requires a controlled restart/redeploy to
guarantee every process sees the new value. Credential rotation must coordinate
new PostgreSQL password, Render secret update and service restart, and revoke
old sessions. PostgreSQL role provisioning and rotation must be performed
against a disposable database first. Do not use production credentials in CI.

## Auth0 staging prerequisites

1. Configure a **separate staging Auth0 Regular Web Application** and HTTPS
   callback URL at the actual staging BFF origin, e.g.
   `https://<staging-bff-host>/auth/callback`.
2. Configure exact Allowed Callback URLs and Allowed Logout URLs; do not
   wildcard or reuse the public GPT Site origin.
3. Provide staging-only `AUTH0_ISSUER`, `AUTH0_CLIENT_ID`,
   `AUTH0_CALLBACK_URL` via Render environment settings. Keep any client
   secret server-side if required by Auth0 app configuration.
4. Obtain issuer metadata and JWKS through trusted HTTPS discovery with
   bounded caching and key rotation; validate ID-token signature, issuer,
   audience, expiry, nonce and `azp` where applicable.
5. Exchange authorization code server-side using PKCE, consume state once,
   issue opaque HttpOnly/Secure/SameSite session, and verify account ownership.
6. Run browser login, logout, replay, expired-state, wrong-nonce, wrong-audience,
   CSRF, token endpoint redirect and account-isolation acceptance tests.
7. Independent security review and explicit staging approval are still required.

**Status:** preparation only. No Render env group, Auth0 application, live
callback, credentials, or services have been created or modified.
