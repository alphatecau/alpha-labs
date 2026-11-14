# Auth0 session and recovery acceptance — isolated CI

## Scope

This gate exercises disposable PostgreSQL 16 only. No external Auth0 tenant,
persistent Render database, production endpoint or trading engine is contacted.

The acceptance suite checks:

- Atomic OAuth state consumption across new database connections
- Six simultaneous attempts to consume the same OAuth state: exactly one success
- Expired OAuth states rejected
- Different OIDC identities produce distinct owner IDs
- Revoked and expired sessions rejected
- Forged session identifiers rejected
- Simulated transaction interruption rolls back an uncommitted OAuth-state delete
- Committed session revocation remains effective across database connections

## Limitations and release gate

These tests do not simulate an actual PostgreSQL process crash, network
partition, database restore, real browser interaction, external Auth0 signing-key
rotation or independent tenant data access under distinct restricted roles.
Existing CI role-grant tests cover a separate, narrower privilege boundary.

Do not treat green CI as evidence of hosted Auth0 acceptance or independent
security certification. Staging remains blocked pending an isolated database,
restricted runtime provisioning, secured secrets and real-browser acceptance.
No production release or live trading is authorised.
