# Alpha Labs paper status staging — NOT APPROVED TO DEPLOY

This blueprint is preparation only and **must not be applied** until security
review and owner authorisation. No public paper trading or broker execution.

- A dedicated Render Starter instance with persistent disk is specified because
  ephemeral free storage cannot safely hold the SQLite journal. Verify Render
  blueprint support, disk pricing, backups and restore procedures before use.
- Staging boot refuses to start without a 32-byte-or-longer base64 signing key,
  issuer, audience, explicit owner subject and existing absolute data directory.
- Signing key and owner subject are entered as server-side environment secrets,
  never committed to GitHub or exposed to GPT Sites.
- GET /api/research/paper/status is the **only** application route.
- No token issuance endpoint is provided. A real identity-provider integration,
  revocation and key rotation are still required; this HMAC research verifier
  must not be treated as production login.
- The owner is pre-provisioned from trusted environment configuration, never
  created from a public request. The data store is single-instance and not a
  multi-user account database.
- TLS termination, CORS/origin policy, rate limiting, security logging, backups,
  recovery and staging end-to-end tests remain unverified.
- The deployment blueprint deliberately specifies a research branch and disables
  automatic deployments. It does not create a Render service by itself.
- Do not connect the public website until authenticated staging is independently
  verified. Do not expose execute/enable routes or any broker connectivity.

**Gate: NO-GO** until all outstanding controls are verified.

## Security regression coverage — follow-up

Added end-to-end WSGI contract tests that instantiate the real staging
factory and local durable account store. The tests cover valid owner status,
missing credentials, forged identity via a valid but non-owner token,
wrong audience, expired credentials, malformed Unicode bearer tokens,
spoofed user headers, query tampering and unsupported enable/execute/live-copy
routes. The verifier now rejects non-ASCII payload segments fail-closed.
These are offline deterministic tests; they do not exercise Render TLS,
external identity provider, multi-process database concurrency or the GPT Site.
