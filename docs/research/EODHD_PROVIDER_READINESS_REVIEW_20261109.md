# EODHD provider readiness review — 2026-11-09

**Decision: NO-GO for live provider use, commercial redistribution, strategy promotion, or execution.**
Research adapter remains disabled by default. No credentials or real provider requests were used.

## 1. Credentials in URL: HIGH
EODHD's documented API requires `api_token` as a URL query parameter. Even HTTPS does not prevent the full URL from appearing in application logs, APM spans, proxy access logs, exceptions, debug traces, redirects or support bundles. The current optional Python transport constructs that URL and relies on the surrounding runtime for logging controls. It does not independently establish end-to-end secret safety.

Required: server-only secret manager; no browser token; prohibit full-URL logging; sanitise upstream exceptions and telemetry; deny redirects; HTTPS validation; allowlisted hostname; TLS-inspecting proxy review; restrict outbound network; credential rotation procedure. Do not enable `ALPHA_EODHD_NETWORK_ENABLED` before independent threat review.

## 2. Licence: BLOCKED
Official terms define business use as professional/commercial. Personal subscriptions prohibit redistribution. Alpha Labs is intended to serve multiple users commercially; neither personal-use rights nor the open-source MCP server licence grants market-data redistribution rights. Obtain explicit vendor commercial agreement specifying: internal research, historical storage and retention, derived indicators/signals, client display, multi-user SaaS, redistribution, geography, exchange-level pass-through fees, audit and termination. No rights inferred from public demo endpoints.

## 3. Provenance: INSUFFICIENT
SHA-256 over the raw JSON protects only the exact captured bytes. It is not provider authentication, a signed timestamp, point-in-time snapshot or an entitlement record. Add: authenticated ingestion record with UTC request/receipt times; provider hostname, dataset, exchange, symbol, requested window, adjustment policy, entitlement reference and licence version; raw immutable snapshot digest; ingestion code revision; source capture ID; correction history; independent verification of snapshot and archive chain. Avoid recording tokens or full URLs. No strategy promotion on hash alone.

## 4. Data semantics: REQUIRES VALIDATION
Official EODHD documentation states EOD OHLC are raw, adjusted_close reflects splits and dividends, and volume is split-adjusted. Historical adjusted closes may be recomputed retroactively. Current parser omits adjusted_close and corporate actions, so it cannot support validated total-return calculations, corporate-action-aware NAV, split-aware volume-dollar calculations, or point-in-time backtests. Daily bars lack executable bid/ask and fills. Treat as unverified research inputs only.

Required independent tests before enabling: vendor demo or licensed fixture capture with immutable receipt evidence; compare AAPL.US and SPY.US raw/adjusted series with corporate actions and a second independent source; check trading calendar, holiday and exchange time zone, duplicate/missing bars, delistings/symbol changes, as-of timestamps, revision drift, survivorship bias, and point-in-time availability. Confirm price/volume adjustment consistency; test negative/corrupted/empty/provider-error fixtures. Record discrepancy thresholds before inspection.

## 5. MCP server boundary
Official MCP server exposes 88 tools, including three report-generation actions, and accepts credentials through several request channels. Do not connect the entire upstream MCP server to autonomous agents or expose it publicly. Existing Alpha Labs adapter is deliberately not an MCP installation or enabled agent tool. Independent security and tool allowlist review required before any MCP connection.

## References
- https://eodhd.com/financial-apis/terms-conditions
- https://eodhd.com/help/commercial
- https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
- https://eodhd.com/help/methodology
- https://github.com/EodHistoricalData/EODHD-MCP-Server/blob/main/README.md

## Acceptance gate
NO-GO until (1) written commercial permission appropriate to use; (2) threat-reviewed credential-safe outbound boundary; (3) provenance and point-in-time evidence; (4) independently reconciled corporate-action-aware fixtures; (5) deterministic CI and separate explicit approval. Live trading remains disabled regardless.
