# Alpha Labs — UI implementation sequence within the locked 26-week programme

This is a **dependent subplan**, not a competing release timetable. Do not advance paper controls before independent server-side risk service and ledger are proven.

| Window | Task | Evidence | State |
|---|---|---|---|
| Weeks 1–4 | Preserve existing site; implement design tokens, four-tab shell, safe empty/synthetic fixtures; add screen-contract tests | 27 existing tests still green, responsive screenshots, all synthetic labels | PLANNED |
| Weeks 5–7 | Design/read-only market status and instrument quality screens, provenance manifests | Real backend data contract tests, stale data gating | PLANNED |
| Weeks 8–13 | Research, intelligence and backtest UI; trial IDs, uncertainty and cost presentation | No look-ahead data exposure, refusal reason evidence, benchmark parity | PLANNED |
| Weeks 14–16 | Risk status, shadow decisions, no broker order buttons | Fail-closed state display, data freshness and source validation | PLANNED |
| Weeks 17–20 | Paper order/activity and reconciliation views following independent risk checks | Unknown fill, duplicate order, trade reversal, stale feeds, halt test | PLANNED |
| Weeks 21–22 | Agent monitoring (read-only), alerts, PWA install experience, authenticated private beta | Measured token budgets, offline/mobile tests, accessibility | PLANNED |
| Weeks 23–26 | Security, usability, operational audits, public informational site accuracy | Threat review, UI audit, valid finance disclosure, no false profit claims | PLANNED |

## First UI sprint (5 work sessions, Android development through cloud)
1. Snapshot the v0.5 website, run existing 27 frontend tests, save baseline and capture current navigation.
2. Define `theme.css` and `Shell` navigation; show DEMO/RESEARCH mode and as-of indicator; do not add fake portfolio account data.
3. Implement Home no-data view and fixtures with prominent `SYNTHETIC` tags; make placeholder states obvious.
4. Implement Markets/Intelligence/Activity skeletons with data-shape contracts and actual empty/error states; map legacy pages under Advanced.
5. Test at 320/360/393/412 CSS px, keyboard, reduced-motion, 200% zoom; record screenshots, tests and differences in `PROJECT_STATUS.md`.

## Definition of done per screen
- Correct mode/status/last-update label, server authority, empty states and screen-reader description.
- Economic metrics have period, currency, provenance, real/paper/research type and honest cost breakdown.
- Does not enable trading or reconfiguration not permitted by the server.
- No data ambiguity under network interruption, missing data and late market events.
- Correctly identifies shortable vs non-shortable instruments without guessing.
- Nav latency and chart payload targets checked on Android-class devices.
