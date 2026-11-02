# Screen-state matrix and test cases

## Global modes and edge cases

| Condition | UI must display | Server-side action / proof |
|---|---|---|
| Not authenticated | Public information or sign-in prompt | No private API data disclosed |
| No account/portfolio connected | `No account connected`; no fabricated equity | Account reference null |
| Research using synthetic fixtures | `SYNTHETIC / RESEARCH` repeated on cards, chart and exports | Fixture data cannot enter broker workflow |
| Shadow with live data | `SHADOW: no orders sent` and feed freshness | No execution credentials on shadow path |
| Paper with unverified broker fill | `UNKNOWN: reconcile required`, no claimed gain | Risk gates block increasing exposure |
| Forecast data expired | `STALE — new entries blocked` | Risk service rejects corresponding proposals |
| Funding / borrow data absent | `COST DATA MISSING` and no net-advantage score | Instrument policy blocks promotion |
| Account short not authorised | `SHORT RESEARCH ONLY` | Server eligibility denies short order |
| Margin headroom insufficient | `REJECTED — insufficient headroom` | Independent risk veto |
| Strategy model version mismatch | `STALE STRATEGY VERSION` | No trading state transition |
| Risk HALTED | `HALTED — new exposure blocked` | Policy in server, authorised reduce/close only |
| Phone offline | `OFFLINE — last known at <time>` | Cloud risk monitoring continues independently |
| API unauthorized / expired session | Reauthentication, no stale personal data persistently displayed | API 401/403; invalidate session |
| Broker position differs from ledger | `RECONCILIATION REQUIRED` | Freeze expansion, log incident |
| Data provider outage | `DISCONNECTED` / `DEGRADED`; never `Live` | Data-quality and policy test |
| Empty performance interval | `No results for selected period` | No interpolated/fake line |
| Positive unrealised P&L | `Unrealised` explicitly | Do not blend into realised total |
| Paper profit | `Paper P&L` and exact model type | Cannot claim actual live trading profit |

## Event sequence tests

1. Risk veto after bullish signal => no order; all rejection reasons visible.
2. Long reversal to short => confirmed close/reconciliation before opening the other side; no double risk.
3. Partially filled order during lost network => ambiguous until reconciled; no duplicate submit.
4. Mid-session currency change => values convert with FX source/time and precise ledger; not silent arithmetic change.
5. Android user backgrounds the browser => engine remains server-side; stale screen must refresh on foreground.
6. Agent produces confident wrong answer => does not bypass forecast calibration or risk veto.
7. Export journal => same signed amounts and order IDs as read-only account view; no credentials/tokens included.
8. Keyboard, screen reader and zoom at 200% => all essential content and controls accessible.
9. Attacker changes client mode chip manually => server permissions unchanged; live order route absent.
10. Stream event gap => snapshot resync; no out-of-order balances silently accepted.

## Nonfunctional release check

- Focusable labels, colour-independent actions and statuses, reduced-motion setting.
- Touch areas target >=44×44 CSS px; 320px screen has no cut-off risk or emergency controls.
- Explicit network/data-source stamps for all signal and portfolio metrics.
- Auth, session handling and server-side risk boundaries reviewed against relevant OWASP guidance.
- Source attribution, version hashes, permissions and incident IDs available from Advanced.
