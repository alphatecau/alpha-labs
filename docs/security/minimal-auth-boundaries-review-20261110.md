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

## Internal adversarial code review (not independent approval)
Reviewed OIDC token parsing and trusted proxy boundary against the complete PR source and tests. Identified and patched three weaknesses in the OIDC verifier: ambiguous duplicate JSON members, accepting a conflicting `azp` for a single-audience token, and permissive issuer configuration. Regression tests were added. These findings do **not** establish an independent security sign-off.

### Remaining review questions
- Require an independent reviewer to inspect cryptographic key-selection, signature verification, clock skew, claim type handling, JWKS freshness/rotation and denial behaviour.
- The verifier returns an unvalidated `nonce` for the OAuth callback layer to compare with its server-side state; **the verifier alone is not a complete OIDC login validation**.
- The proxy adapter trusts WSGI `REMOTE_ADDR` only after an operator proves the actual socket-peer source. It must never be wired into Render based on guessed CIDRs or client-supplied forwarding headers.
- Validate proxy Host/port normalisation and intermediary header-stripping with real deployment evidence. Current synthetic tests cannot certify Render topology.
- Ensure there is no path from these primitives to active trading; neither component authorises execution.

**Status:** internal review findings addressed in research branch; independent review and real environment acceptance pending. No merge or deploy approval.
