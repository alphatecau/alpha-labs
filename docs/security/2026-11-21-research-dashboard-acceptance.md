# Alpha Labs research dashboard acceptance

## Deployable components

The public Site Worker requests the existing research results endpoint and the new read-only `/api/v1/research/economics` endpoint. Both require a non-expired server credential and an exact Render revision. The Worker checks the response SHA-256 against its own pin before releasing data.

The Site’s top-level Sign in action hands navigation to the dedicated Auth0 Python BFF. Its callback, opaque session and logout remain on the BFF origin. Both dashboard and API reads use the same current-ownership check and restricted tenant PostgreSQL login. The dashboard displays only the latest 50 account-owned research records. An empty account has an explicit empty state.

## Reproduced historical evidence

The 5 November source ZIP has SHA-256 `80065224b4240412ba61129c4581a16e4ea2944c22509357156bf414d4440485`. With the project source on the Python path, `tools/build_dashboard_evidence.py <archive>` emits the committed economic report on stdout. Every input CSV hash must match the frozen audit. Reference and double-cost replay must match the archived report’s fee totals, closing values and order counts. An additional cash and inventory calculation reconciles all fills. The original audit and EMA(12,48) code are unchanged.

| 10,000 USDT starting balance per market | Net P&L (USDT) | Fill fees (USDT) | Fills | Closed trades | AUD valuation change |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTCUSDT | −1,101.19 | 258.90 | 130 | 65 | −2,112.27 |
| ETHUSDT | −70.93 | 237.94 | 119 | 59 | −570.17 |
| SOLUSDT | −734.62 | 235.26 | 118 | 59 | −1,563.58 |

The unsealed window runs from 15 June 2025 19:00 UTC to 1 January 2026 00:00 UTC, exclusive. AUD marks use the last preceding Kraken USDT/AUD trade at each boundary. Opening and closing prices were 1.543200 and 1.496800 AUD per USDT. Consecutive trade IDs bracket each boundary. The two pinned raw responses and their source URLs accompany the report. AUD change includes currency movement on the entire virtual balance. These are historical valuations. The model executed no AUD conversions and includes no FX fees or spread. Fills are simulated using 10 bps fees and 10 bps adverse slippage per side. Venue fees were not measured for a real account.

## Staging acceptance and release

1. Run the authenticated BFF on a dedicated free staging origin with the isolated configuration described in `deployment/isolated_auth0_wsgi.py`. Allowlist `<BFF origin>/auth/callback` and `<BFF origin>/signed-out` on the existing staging Auth0 application. Keep credentials in the hosting secret store.
2. Verify the separate OAuth, session, ownership and audit database roles and provision two independent research identities through trusted administration. Keep the database on the private network.
3. Set `ALPHA_AUTH_BFF_ORIGIN` on the staging frontend. Exercise login, both dashboards, account switching, expiry and sign-out on an Android handset. Record statuses and redacted evidence. Sign out must revoke the local session before the provider logout redirect.
4. For research rollout, serve both evidence endpoints on the accepted revision, then set the matching Worker revision pin. Check the three historical cards and all 367 fills. A staged Worker with a previous backend shows an unavailable message for detailed economics.
5. Production publishing requires separate approval after hosted acceptance. No execution, leverage or signing endpoint is part of either research service.

Verified in development on Python 3.12 with PostgreSQL 16.2. The Auth0 exchange in integrated tests uses test doubles. The RLS tests use actual separate PostgreSQL logins. The current public Worker returned the three original findings with the Render revision `91ce4ad54fb93956f4001df0b88e533dd59dcb85`. The public service returned 401 for unauthenticated research and 404 for its Auth0 login path. Hosted Auth0 and physical Android acceptance remain open.
