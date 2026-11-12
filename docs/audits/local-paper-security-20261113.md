# Local paper security review · 13 November 2026

| Finding | Resolution and verified scope |
|---|---|
| An incorrect working path could silently initialise a new balance. The previous terminal also ran additive schema creation on a selected legacy file. | Normal startup requires an existing standalone working database and current schema. New initialisation is explicit. The historical directory and file aliases are rejected for writes. Migration is exercised only on an isolated verified copy. |
| A timeout or interruption could lead an operator to retry with a freshly generated ID. | A terminal submission requires a stable ID selected before submission. Reusing committed terms returns the recorded fill, and changing terms under a committed ID fails. SQLite commits the fill and its order state together. |
| Feed loss in the final order check could leave the previous arm in effect. | An invalid final snapshot durably records market-data HALT. Recovery requires manual arming. Fresh but changed snapshots decline the current request. |
| After restart, a same-sequence quote with changed depth could replenish consumed liquidity. | New fill details bind bid, ask and both sizes. Replay rejects conflicting depth. A same-sequence legacy fill without those fields reserves that book from execution until a newer sequence is received. |
| Timestamp rejection alone obscured whether the book was stale or ahead of the device. | The opt-in smoke records exchange time, receipt time, age and request duration. The 500 ms existing transport tolerance remains bounded. The runtime waits for causality before using a book and enforces the 10-second freshness gate. |
| A filesystem backup could be confused with independently authenticated rollback protection. | Recovery reports SQLite structure, event hashes, independent economic replay and backup lineage separately. It can compare a supplied independent sequence and digest. The local journal cannot detect replacement of all local history and comparison metadata. |

Ruff and Bandit medium/high passed on the candidate. The runtime dependency audit reported zero known vulnerabilities for the resolved project dependencies. These are scoped tool observations. The repository's configured CodeQL and Gitleaks workflows provide separate exact-head receipts on the draft. No findings were suppressed.

## Authentication and hosting

The public Auth0 discovery endpoint returned HTTP 200 for issuer https://alpha-labs-dev.au.auth0.com/ and lists S256 and RS256 support. That result verifies public metadata only. Main retains its minimal OIDC verifier and trusted-proxy boundary. The separately tested owner stack at cfef52790c6905182e97ba4df1a72fef82e0b6b8 passed 92 selected authentication and BFF tests plus 68 subtests, and 47 disposable PostgreSQL tests plus 22 subtests. That test suite exercises issuer and audience, code exchange, PKCE, state and nonce, cookies, revocation, CSRF, owner and tenant isolation, quotas and relay credentials.

The actual Auth0 application audience, allowlisted callback, owner/second identity, deployed TLS peer chain and private PostgreSQL trust anchor remain open acceptance gates. No hosted credentials were requested or read. Render returned HTTP 200 and research_only with trading disabled on /healthz, and HTTP 404 for the paper-state route. The Render service metadata identified a free health-probe branch with automatic deployment disabled. The existing public Site request returned HTTP 403 from this execution environment. Hosted owner paper remains NO-GO.

Free local execution meets the A$0 requirement and keeps data in user-controlled SQLite storage. Render's free web tier can spin down and has ephemeral local storage. The free Postgres tier has a 30-day lifetime. These constraints rule out treating the present free service as verified durable journal or checkpoint custody. [Render free-tier documentation](https://render.com/docs/free)

## Market-data usage

Coinbase limits market-data use to the individual or the organisation's internal personal or research scope and restricts third-party distribution of data and derived works. The live terminal profile is limited to that scope. Store its detailed diagnostic output privately and obtain the required provider rights before any wider dashboard or service rollout. [Coinbase market-data terms](https://www.coinbase.com/en-au/legal/market_data)

See [release gates](../operations/local-paper-release-gates.md).
