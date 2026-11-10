# Minimal authentication boundary candidate — independent review required

**Base:** main at 2cb66a8ddfc2d2b64246ab9441d0a26a364f7360.

## Scope
This intentionally narrow PR extracts only two isolated, previously researched **security primitives** and their existing adversarial unit tests:
- `deployment/verified_proxy_ingress.py`: reject unverified socket peers and untrusted/ambiguous forwarding metadata.
- `deployment/oidc_verifier.py`: validate pinned RS256 OIDC ID-token signatures and claims using supplied trusted JWKS.
- Two dedicated unit-test modules and a PR-only CI workflow.

No login routes, Auth0 discovery client, OAuth state/session persistence, PostgreSQL adapter, broker, trading engine, production server entry point, migrations or Render configuration are included. **These primitives are not an authenticated application.** Do not deploy or wire into production on the basis of this PR.

## Independent security review checklist
- [ ] Review actual source and complete diff for authentication bypasses, malformed tokens, issuer/audience/nonce/time validation, key selection and algorithm confusion.
- [ ] Verify trusted proxy peer identification from actual Render socket-level evidence; do not infer from `X-Forwarded-For`.
- [ ] Confirm unit tests run on exact PR head and all repository checks pass.
- [ ] Review origin/host and proxy header contract for the chosen ingress architecture.
- [ ] Obtain independent reviewer approval recorded on this PR.
- [ ] Keep staging deployment NO-GO until separate real Auth0 browser, session lifecycle, two-account database isolation, proxy trust and fail-closed dependency acceptance pass.

## Relationship to research
Source: stacked PR #84. This candidate does not claim to incorporate the entire authentication chain. Preserve PR #84 and ancestors for review until all unique changes are accounted for. The historical 151+ commit research chain is intentionally excluded.

## Non-goals
No merge, deployment, secrets changes, database access, GPT Site modifications, paper trading or live trading.
