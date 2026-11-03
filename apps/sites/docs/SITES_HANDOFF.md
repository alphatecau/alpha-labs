# ChatGPT Sites continuation brief — Alpha Labs v0.3

**Goal:** import the provided website source into an existing/new ChatGPT Sites project, preserve its dark/lime design and seven navigable sections, and deliver a working **private preview** before publishing.

**Source files:** `index.html`, `style.css`, `app.js`, `research-engine.js`, `evidence-engine.js`, plus docs, CSV example and automated tests. Follow the relative file links unchanged. Use the existing code, not a fresh reconstruction of the layout.

**App boundaries:** static browser research only. There is no connected market feed, wallet, AI backend, live P&L or authenticated dataset. Never fabricate these. Mark synthetic data prominently. Do not prompt for trading credentials or introduce transaction-signing logic.

**Functional acceptance:**
1. Navigation works for all seven sections on desktop and mobile.
2. CSV import, backtest, data validation, risk calculations, hypothesis registration and JSON downloads function.
3. Evidence Audit runs four fixed candidates chronologically and warns about unsealed repeated evaluation.
4. Token budget updates when call count/usage/prices change; no AI API call occurs.
5. All numerical outputs are in selected quote units (USDC != AUD); token API price figures are in USD.
6. The tests run with `node --test tests/*.test.cjs` and the live preview is manually inspected. Publishing is a separate action.

**Next development priority, not part of this static source:** evidence-grade market-data provider, locked server-side research protocol, executable quote capture, auditable independent risk engine, and monitored paper-only execution. Follow `docs/PROFIT_SYSTEM_BLUEPRINT.md` and `docs/TOKEN_EFFICIENCY.md`.
