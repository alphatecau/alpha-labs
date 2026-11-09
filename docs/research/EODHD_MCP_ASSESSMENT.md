# EODHD MCP — Alpha Labs research-only assessment

Status: experimental, disabled by default. No external network integration, live API key, MCP connection, trading or deployment.

## Findings

- Upstream repository: https://github.com/EodHistoricalData/EODHD-MCP-Server
- Python upstream >=3.10; Alpha Labs >=3.12: compatible in principle.
- Upstream advertises 88 tools, including three Praams report-generation/email side-effect tools. Do not expose these tools to research agents.
- EODHD API tokens may be placed in query parameters. Avoid URL logging, browser credentials, agent-supplied tokens and unauthenticated public MCP transports.
- EODHD commercial data rights are separate from the software licence. Confirm commercial, redistribution, storage and derived-data rights in writing before operational use.
- Subscription coverage, corporate-action adjustment semantics, publication lag, point-in-time fundamentals, survivorship bias, quote latency, timezone, exchange calendars, corrections and rate limits remain unverified.

## Implemented

A pure, offline EOD JSON parser with two independent opt-in gates, deterministic SHA-256 of original input bytes, chronological OHLCV checks and no transport, credentials or execution hooks. The hash does NOT prove source authenticity. Fixtures are synthetic.

## Before enabling any data ingestion

1. Obtain a commercial licensing determination and suitable provider plan.
2. Implement a separate authenticated server-side provider client, not direct agent-controlled MCP access.
3. Pin endpoint versions and immutable raw response plus request metadata in a trusted evidence store; never persist tokens.
4. Validate point-in-time timestamps, corporate actions, timezone, gaps, revisions, symbol changes, adjustment policy and data lineage.
5. Add deterministic mock transport tests for 401/403/429/5xx, malformed responses, retries, redaction, timeouts and quota exhaustion.
6. Independently compare sampled bars against a second source, then reproduce risk-matched backtests.
7. Obtain separate approval before changing any deployment configuration or allowing network access.

No trading promotion or paper/live execution is authorised by this assessment.
