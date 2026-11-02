# Alpha Labs — Mobile Operator UI/UX Specification v1.0

**Baseline:** Alpha Labs profit-first Master Plan v3 (2 November 2026). **Status:** approved conceptual visual direction, new interface specification proposed; **not yet implemented**. **Client:** Android-first mobile browser/PWA; responsive desktop; private operator console distinct from public informational website.

## 0. Goal, operating principle, non-goals

The primary UX question is: **What is the system doing with capital, is that making or losing money after costs, what risk is being taken, and what evidence supports each decision?** The interface must not imply that simulated, backtested or hypothetical profits are realised.

Design principles: (1) immediate financial truth, (2) visible mode and safety state, (3) progressive disclosure, (4) evidence behind every signal, (5) one primary action per screen, (6) mobile one-hand interaction, (7) no fake market data or unsupported certainty, (8) trustworthy failure states, (9) no user-facing complexity from agent internals, (10) independent server authority for all controls.

Explicit exclusions in first six months: live execution UI, wallet/private keys in browser, AI-driven risk-policy edits, social trading, deposits, leverage up-selling, animated profit claims, continuous phone-based trading processes, gamified trading prompts, automatic short selling when account not eligible, predictions labelled as calibrated probabilities without validation.

## 1. Information architecture

Public website (`www`): product explanation, research principles, security and risk disclosures, roadmap, access/login entry. No personal positions or trading account data.

Private operator console (`app`): persistent navigation **Home | Markets | Intelligence | Activity**. Top chrome: ALPHA LABS wordmark, account/mode chip, data freshness/safety status, overflow/settings entry. Bottom navigation on mobile; left sidebar desktop. Advanced workspace via Settings > Research & System.

Research/Advanced retains existing v0.3 functions: Overview -> Home or reference; Alpha Research -> Strategy Lab; Backtest Studio -> Backtest Studio; Evidence Audit -> Evidence; Risk Laboratory -> Risk Sandbox; Development Plan -> Roadmap; Architecture -> System Architecture. Preserve existing JavaScript module and regression tests until equivalent functionality is verified, rather than removing them during redesign.

### Navigation and screen map

```
PUBLIC SITE
  /                 Public Alpha Labs product site (no portfolio values)
  /research          Methodology and evidence policy
  /risk              Trading risk and product disclaimers
  /login             Authenticated console entry

PRIVATE APP [authentication required]
  /app/home          Financial state + safe operations
  /app/markets       Monitored instruments + eligibility + signals
  /app/intelligence  Decisions, critiques, rejected opportunities
  /app/activity      Position/trade/decision/incident audit journal
  /app/settings      Preferences, security, notifications, data sources
  /app/advanced      Collapsed gateway to engineering/research workspaces
    /strategy-lab    Hypotheses and trial registry
    /backtests       Backtest Studio
    /evidence        Walk-forward/holdout and provenance
    /risk-lab        Risk sandbox/policy diagnostics
    /operations      Agent health, jobs, model versions, restarts
    /architecture    Architecture and development roadmap
```

## 2. UI layout and visual tokens

Theme (dark default): background `#101419`, elevated surface `#192028`, higher surface `#202A26`, border `#303B42`, primary text `#F5F7F6`, secondary `#98A5AF`, positive `#B7F486`, negative `#FA8686`, warning `#F2CB79`, neutral action `#CED7DD`. All finance-significant changes must be conveyed with words and icons as well as colour. Positive green is not used for the 'LIVE' badge so it cannot be mistaken for profit.

CSS token suggestions: `--radius-sm: 10px`, `--radius-md: 14px`, `--radius-lg: 18px`, `--spacing-unit: 4px`, core margins 16px mobile / 24px tablet, typography system sans/Inter fallback, title 22–26px mobile; summary equity 28–34px, supporting text 12–15px with accessible scaling. Data numbers use tabular numerals. Use `font-variant-numeric: tabular-nums`, `prefers-reduced-motion`, visible keyboard focus and tested contrast. Target WCAG 2.2 AA. Primary touch targets 44×44 CSS px or larger (design target, beyond the WCAG 2.2 SC 2.5.8 24×24 minimum with exceptions).

Breakpoints: narrow phone 320–374px; standard 375–599px; tablet 600–1023px; desktop >=1024px. Bottom nav at phone, optional rail at tablet, left sidebar at desktop. Avoid horizontal scroll on trading controls. Persist chart range per user; respect Android system font scaling. Safe-area insets and virtual keyboard must not cover important buttons.

Charts: default a single portfolio-equity line, period selector 1D/7D/30D/ALL where data coverage exists, annotations for deposits/withdrawals and strategy-mode changes. Label synthetic or incomplete runs visibly. Use no chart when observations are unavailable. TradingView Lightweight Charts is a candidate (Apache-2.0; verify attribution obligations and license version before integration).

## 3. Modes, safety state, and truthfulness

Mutually exclusive **mode**: `RESEARCH`, `SHADOW`, `PAPER`, `LIVE` (LIVE is unimplemented/forbidden without independent G7 approval). Separate independent `safety_status`: `NORMAL`, `RESTRICTED`, `HALTED`, `RECOVERY_PENDING`. Separate `data_status`: `FRESH`, `DELAYED`, `STALE`, `DISCONNECTED`, `UNKNOWN`. Mode/safety/data labels all visible; no inferred 'healthy' or 'live' from a connected browser.

- Research: historical simulations only; currency returns marked `BACKTEST`. No position controls.
- Shadow: live observation and hypothetical actions, no broker order requests; mark `SHADOW`.
- Paper: risk-authorised simulated broker, modelled fills; mark `PAPER`, never present as real profit.
- Live: withheld UI route and server capability until policy, venue, security and capital approval; if ever implemented, require distinct deployment, explicit unlock workflow and step-up auth. No 'switch to Live' toggle.
- Halt: block opening/increasing exposure at server; only authorised monitoring, reconciliation and close/reduce are allowed. A UI button cannot be the only enforcement point.

Disambiguate `demo` content: demo is an independent visible flag, not a substitute for paper; `SYNTHETIC` must be displayed on each relevant chart/table and exported report. All profit numbers require provenance (`simulated`, `paper_modelled`, `broker_confirmed`, `reconciled`) and UTC/as-of time.

## 4. Home — question answered in under five seconds

Screen order, mobile:
1. Wordmark / active account alias and unmistakable mode chip (`RESEARCH` initially).
2. Status strip: Data freshness (`Updated 22:14 AEST`, or `STALE — trading restricted`), server health, policy state. Time display local Australia/Brisbane, server preserves UTC.
3. Capital panel: portfolio equity / buying power / collateral separated, currency AUD with native quote-currency detail available. For research, do not show fictitious personal capital; use a visibly labelled example or `No account connected`.
4. Net P&L panel with realised, unrealised, financing/fees, platform operating costs and selected period; show `N/A` if unavailable, not zero. Do not label 'after tax' without tax computations.
5. One uncluttered equity/return chart with benchmark toggle and cash-flow annotations; show data provenance and sample coverage.
6. Current exposure card: total signed notional, each active instrument, LONG/SHORT/FLAT, entry/mark, protective risk state, margin/headroom, liquidation if relevant and verifiable. No leverage badge if not applicable.
7. Latest decision: `FLAT — forecast edge below costs`, timestamp, link to evidence. If not assessed, `Not evaluated`.
8. One visible primary safety affordance: **Pause new entries** in paper mode (server-authoritative and requires confirmation); **Resume** gated by reconciled state and optional reauthentication; never show active trade controls in Research.

Empty state: `No live account or paper broker is connected. Research mode only.` Offer `Open Backtest Studio` link; never a fabricated A$10,000 portfolio presented as factual.

## 5. Markets — not a slot machine

Default universe: BTC, ETH, SOL, labelled **research watchlist**, not automatically executable markets. Each compact row: asset/contract + venue; 24h change or relevant period; regime; candidate direction `LONG`, `SHORT`, `FLAT` or `NOT EVALUATED`; expected net edge *with validated units and forecast horizon*; trading eligibility `RESEARCH ONLY` or `ELIGIBLE` and quote freshness. Include source and as-of timestamp. A score is not a probability without documented calibration.

Asset detail: multi-timeframe chart, price/mark/index/bid/ask properly differentiated, executable/quote info, volatility, funding/borrow, risk scenario, strategy version, latest rationale, regime, eligibility verification, data-quality issues. Advanced indicators behind an accordion.

Filters: watchlist, venue, signal, eligibility, freshness. No 'best coin' hype or ranking merely by price appreciation. Clicking an asset never submits a trade.

## 6. Intelligence — explainability and abstention

Primary card: `Current assessment: LONG/SHORT/FLAT/UNAVAILABLE`, instrument/horizon, observation time, model version, conservative net expected return or `UNAVAILABLE`, uncertainty and at least one high-salience opposing fact. Show a calibrated probability **only** with calibration evidence; otherwise say `model score` or descriptive signal. Include source data links, costs and reasons no trade occurred.

Sections: `Why this decision` (up to 3 plain-language facts), `What could invalidate it`, `Trade rejection reasons` with all hard-veto reasons, `Forecast vs outcome` (once outcome known), `Agent insights` summarised and clearly distinct from deterministic policy. Keep individual agent chats and verbose prompts in Advanced > Operations.

Audit affordances: tap `View evidence` to see full immutable trial/decision IDs and timestamp lineage; `Report issue` creates an incident/report, never modifies the decision.

## 7. Activity — exact separation between forecasts, orders and money

Top filter: `All`, `Decisions`, `Orders`, `Positions`, `Incidents` and `AI cost`. Every timeline entry has action, instrument, mode, time, status and immutable identifier. Paper trade timeline: strategy signal -> proposal -> risk checks -> accepted/rejected -> submitted -> partially filled/filled/expired/cancelled/unknown -> reconciled. Unknown remains `UNKNOWN`; never 'successful'.

Trade detail: entry/exit, signed units, notional and settlement currency, venue, quote, realised/unrealised P&L, fees, funding/borrow, FX to AUD, simulated vs reconciled classification, available source receipts, and adverse-execution difference. Show reason for rejection (risk, stale data, insufficient edge, unapproved instrument, margin) and opportunity-cost caveats.

`Profit leakage` report partitions pre-cost forecast vs actual/modelled result into spreads, fees, funding/borrow, impact, failed orders, latency and operational/AI costs. Do not attribute unexplained residuals to a made-up category. Export redacted CSV/JSON with permission check.

## 8. Settings and Advanced

Settings: account/profile, local time and AUD currency preference, notifications, reduced motion, data-provider diagnostics, session security, MFA, authorised devices, model/market-data build versions and logout. Agent token budgets visible but not agent-configurable.

Advanced access: research experiments, backtests, evidence audit, risk lab, system logs, state recovery and signed release manifests. Research controls may permit new trials but never modify a deployed model during an active forward test. Existing seven-section static website functions migrate here, with feature parity tests.

## 9. User flows and exact safety behaviour

- First visit (no account): shows public site; sign-in required for private console.
- First app open (no data): real empty state and direct Research onboarding, no apparent profit chart.
- Routine Android check: unlock securely, see current mode + stale status, net equity, exposure, decision, and last reconciliation time.
- Investigate a short signal: Markets > instrument > Intelligence evidence > cost/funding > risk result; viewing cannot trade.
- Investigate a loss: Home period -> Activity trade -> accounting decomposition, cost leakage and strategy/version link.
- Data stale: prominent warning and server restricts new orders; unchanged historical chart may be shown but labelled stale.
- Broker ambiguous fill: show `RECONCILIATION REQUIRED`, block increasing risk, alert operator; no client-side optimism.
- Halt paper trading: explicit button -> confirmation -> authenticated POST to independent risk API -> show HALTED only after acknowledged status from backend -> explain how monitoring and reduce-only continue.
- Resume after halt: reason cleared, reconciliation complete, operator permission validated, step-up auth where appropriate, server approval; no direct 'one tap' resume.
- Lost phone/mobile offline: backend continues monitoring and paper risk checks; UI shows last known timestamp and offline indicator; no client background trading dependency.
- Future live pilot: not part of current build; separate security protocol, account and capital authorisation required before exposing controls.

## 10. Required API and event contracts (proposed, not implemented)

Every response has `schema_version`, `request_id`, server `as_of_utc`, `mode`, data `provenance`, `quality` and permission-scoped content. All monetary amounts use decimal strings and declared currency; all quantities declare unit/contract multiplier. Don't expose API keys or signing credentials.

Read endpoints (private):
- `GET /api/v1/session` authentication and allowed roles
- `GET /api/v1/system/status` runtime, safety, feed freshness, reconciliation
- `GET /api/v1/portfolio/summary?mode=paper&period=30d` equity, P&L components, funds, provenance
- `GET /api/v1/portfolio/equity-curve?period=30d` plot data plus cash-flow events and benchmark
- `GET /api/v1/markets` contract registry with research/execution eligibility
- `GET /api/v1/markets/{instrument_id}` asset market state and source trace
- `GET /api/v1/decisions?limit=...` recent long/short/flat/rejected decisions
- `GET /api/v1/decisions/{id}` input hashes, model, forecast, cost, risk vetoes
- `GET /api/v1/positions` signed exposure with mark/index and margin context
- `GET /api/v1/activity` immutable timeline, cursor-pagination
- `GET /api/v1/analytics/profit-leakage` gross-to-net audited decomposition
- `GET /api/v1/operations/agents` health, budgets, tasks, without raw secrets

Write (paper only; protected by role/MFA/CSRF/idempotency as appropriate):
- `POST /api/v1/paper/entries/pause` with confirmation, operator identity and unique key
- `POST /api/v1/paper/entries/resume-request` (request only; server checks policy)
- `POST /api/v1/research/experiments` in sandbox permissions
- `POST /api/v1/incidents` record operator concerns

The UI never calls brokerage/DEX order APIs directly. All order handling occurs within server execution boundary. Prefer HTTPS and secure cookie sessions with CSRF protection and explicit authorization; audit high-impact operations. Real-time WebSocket/SSE stream is read-only, versioned and sequence-numbered; on gaps or reconnect, fetch authoritative snapshots.

## 11. Accessibility, reliability, privacy and telemetry

Accessibility: WCAG 2.2 AA target; semantically labelled controls; high-contrast text; non-colour signs for LONG/SHORT and P&L; logical focus; keyboard support; screen-reader announcements for critical state changes (rate-limited, no flashing), supports 200% zoom and reduced motion; generous touch areas.

Performance targets (design targets, not verified): first useful render <3 s at typical Android 4G; interactive navigation <300 ms for cached screens; chart draw <1 s after data receipt for standard sample; no more than one persistent streaming connection per active session. Instrument and period limits must avoid enormous mobile payloads. Test under throttled network and older Android phones.

Reliability: visible stale/unknown states; no false `online` badges; requests cancel on navigation; authoritative server source; read-only cached historical material clearly labelled and timestamped; retry idempotently and with bounded backoff. App remains safe when offline or Android process is killed.

Security/privacy: private console requires authentication and least-privilege roles (`VIEWER`, `PAPER_OPERATOR`, `ADMIN`); protect admin with MFA; short-lived sessions and revocation; deny-by-default API authorisation; server-side secrets; audit export redaction; no sensitive market/broker credentials in localStorage, analytics or LLM logs; security headers and CSP; no direct order credential on device.

Privacy: default minimal telemetry with no market account identifiers in third-party analytics. Legal/compliance review before public trading services or sharing performance claims.

## 12. Content style, error and audit language

Preferred: `No strategy passed validation`, `Estimated net edge after modeled fees: +0.14% (unverified)`, `Short not available on this instrument`, `Funding data unavailable — trading blocked`, `Paper order fill unknown`, `No live account connected`, `Research result: not evidence of live profit`.

Forbidden: `AI guarantees 88% wins`, `live profit` for synthetic paper data, `confidence 92%` without calibration, `safe`/`risk-free` for derivatives, `success` while broker status is unknown, `updating` when feed is disconnected.

Numbers: sign and units always included. Display `+A$123.45` or `−A$23.00`, with clearly stated period, profit type, current FX conversion provenance and rounding; the authoritative ledger holds full precision. Use `N/A` for unavailable instead of silently manufacturing 0.

## 13. Design acceptance criteria and delivery gates

UI-0: Static site retains 27 existing tests and research functionality; all demo figures labelled; new navigation responsive.
UI-1: First use/no-data and all 4 primary screens verified with fixtures; no active controls or profits shown without backend truth.
UI-2: Data contracts implemented/validated; stale/unknown/missing/partial states and server-mode mismatch tested.
UI-3: Read-only research/shadow app can render verified provenance, decisions and cost estimates with accessibility checks.
UI-4: Paper mode appears only after independent risk and paper ledger approval; halt/resume commands audited and server-authoritative; broker failure injection performed.
UI-5: Operator beta: pass Android tests on 320/360/393/412px and tablet/desktop, voice/screen reader and keyboard checks, network loss/recovery, high font scaling, session expiration, no critical security findings; all costs and reported profits reconcile with the backend.
UI-6: Public site legal/disclosure and claims review; source and build versions visible; no promised profit claims.

**Unresolved:** Actual eligible venue and contract, funding/borrow history, capital/loss budget, secure hosting and user identity management. UI must represent these as `UNVERIFIED`, not silently assume them.
