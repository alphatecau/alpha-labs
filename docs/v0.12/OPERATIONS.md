# Local operator and recovery runbook

Requires Python 3.12+. No exchange account, broker key, AI tokens, paid service or production deployment. These commands operate a local synthetic account only.

## Start the terminal (including Android Termux)

From the repository root:

```sh
export PYTHONPATH=packages/alpha_lab/src
python -m alpha_lab.paper.cli serve --state-dir "$PWD/.alpha-paper" --port 8765
```

Open `http://127.0.0.1:8765/` in a browser on the same device. The server creates two separate local demo operators, Alice and Bob, and a private `.alpha-paper/operator-tokens.json` file. Copy one token into the password field without publishing it. Tokens expire after one hour and are replaced on process restart; sign-out revokes that token. They are **local development tokens**, not brokerage credentials. The runtime directory is private and ignored by git. No native device test was performed by the author.

1. Inspect the account, fixed risk limits and strategy evidence.
2. Open Control centre and Enable simulation.
3. Run synthetic cycle. Inspect the committee, order/fill events, equity and reconciliation.
4. Apply synthetic gap to observe a stop exit at the adverse observed fixture price, or close the simulated position.
5. HALT blocks new entries and cancels pending orders. It does not liquidate positions. Reduce-only closure remains separately checked.
6. Review/clear HALT only after closing positions and reviewing the incident; enabling is a separate action. Daily/drawdown loss anchors are not reset.
7. Export my records downloads only the authenticated account snapshot and last 200 journal events. Full local audit history is retained in the DB; this is not a completed customer deletion/portability service.

Do not expose this development server with tunnels, bind it publicly or add production tokens. Existing Sites production/UI hosting is untouched.

## Diagnostics / deterministic replay

```sh
export PYTHONPATH=packages/alpha_lab/src
python -m alpha_lab.paper.cli replay > /tmp/alpha-replay-a.json
python -m alpha_lab.paper.cli replay > /tmp/alpha-replay-b.json
cmp /tmp/alpha-replay-a.json /tmp/alpha-replay-b.json
python -m unittest discover -s tests/paper -p 'test_*.py' -v
```

The replay uses synthetic prices, includes entry and gap-stop exit, reconciles primitives and checks the other tenant is unaffected. It is not a financial return estimate. `paper/runner.py` also accepts bounded async simulation events and halts on provider failure/timeout. No daemon or deployment schedule is installed.

## Backup and recovery

Use `Store.backup(new_path)` through a trusted local Python operator process; it uses SQLite's backup API for a consistent copy. Do not copy only the DB file while WAL writes are active. Keep backups private, outside git and separate from the running state. Restore into a **new** file and run `ledger.reconcile` and `verify_audit` before reviewing entries. The automated restore test verifies cash, position, fee and journal parity; no production RTO/RPO is claimed.

Startup checks reconciliation, cancels unresolved orders, preserves HALT and suspends entries. It never retries an ambiguous fill or re-enables trading. If corruption is detected, keep the account HALTed, preserve evidence and use a reviewed backup. A local hash chain cannot prove completeness against an administrator rewriting or truncating the whole store; production requires independent immutable retention and external audit-head custody.

## Failure interpretation

| Observation | Meaning / action |
| --- | --- |
| Access denied | Missing/expired/revoked token, wrong tenant/role, or invalid Host/Origin; inspect identity instead of adding client-supplied identity headers |
| UNVERIFIED / historical rejection | Strategy cannot execute. Preserve its previous failure and collect independent evidence in research |
| DATA_INVALID_OR_STALE | Quote timing/identity/causality failed; HALT persists; do not refresh an old event's receipt timestamp to hide age |
| REJECTED at fill | Current price, costs, limits or connectivity no longer permit the proposed remainder; inspect the recorded reasons |
| Reconciliation failed | Stop entries, preserve DB/WAL and audit evidence, review/restore a trusted copy |
| No real market prices | Expected: real feeds, broker sandboxes, licences and eligibility are not connected |

For future production, define on-call ownership, incident severity, revocation, external alerting, availability/latency budgets, clock synchronisation, encrypted backups, retention, drills and independent recovery acceptance before launch. None is established by passing these local checks.
