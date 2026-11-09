# Alpha Labs — external evidence and provider precision contract

**Research-only.** No live trading, broker API calls, secrets or commercial data required to exercise synthetic tests.

## Independent external evidence acceptance
1. Obtain an independently downloaded broker/exchange statement from a source controlled by the account owner. Do not paste credentials or signed download URLs into GitHub.
2. Preserve original bytes in a private evidence vault; record SHA-256, file size, UTC retrieval time, provider identifier, account pseudonym and source document period. A digest alone proves integrity, **not** source authenticity.
3. Verify source independently through provider authentication or a signed attestation. Until verified, classify as `UNVERIFIED_EXTERNAL`, never `AUTHENTICATED_EXTERNAL`.
4. Map statement executions to canonical fill IDs, UTC timestamps, instrument, side, quantity, price, quote currency, fee amount/currency and cash delta. Reject duplicates, missing records, unsupported fee currency, FX or instrument conventions.
5. Reconcile cash, inventory, fees, realised/unrealised P&L and liquidation NAV independently. Reject discrepancies; do not overwrite or adjust the independent statement to match the model.
6. Archive reconciliation result and explicit evidence status. Never promote unauthenticated evidence to profitability claims.

## Provider-specific numeric contract
- Currency minor units, minimum price tick, quantity step and lot size MUST be sourced from provider/instrument metadata and recorded with timestamp and version.
- Explicitly define whether each fee is rounded at execution, settlement or statement posting. Do not assume AUD cent rounding for BTC/ETH/SOL quote currencies.
- Decimal inputs are currently bounded to 28 significant digits and adjusted exponent ±18; these are **research input limits**, not a verified exchange policy.
- Current `quantise_aud` is illustrative and not automatically applied to order ledgers. Settlement policy is **UNVERIFIED** until provider evidence exists.
- Reject unsupported derivatives, margin, short positions, cross-currency fees and corporate actions. Never silently coerce.
- Test boundary values at tick/lot edges and partial-sale cost basis before accepting any provider adapter.

## No-credentials workaround
Use deterministic synthetic fixtures and independently constructed mathematical NAV/P&L oracles for software correctness. Public historical candles may support *research* if their licence and timestamps are verified, but cannot authenticate private execution fills. Real external statement reconciliation remains **BLOCKED — owner/provider evidence required**.

## Release gate
CI green + deterministic accounting oracle does not equal authenticated market evidence. Keep draft PR and trading/deployment disabled until independently verified external evidence and instrument settlement policies are supplied.
