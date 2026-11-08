# Alpha Labs architecture audit and chronological evidence milestone

Audit basis: main branch at `9d705bd` plus draft PR #15. No production or trading changes.

## Inspected components

| Component | Current behaviour | Finding |
|---|---|---|
| `data/csv_import.py` | Strict UTC OHLCV interval, numeric and checksum validation | File integrity is not independent venue price authenticity |
| `backtest/engine.py` | Next-open long-only simulated execution; orders and summary P&L | No chronological NAV or per-period return export |
| `research/walk_forward.py` | Rolling 168-hour windows, EMA 12/48, benchmark and double costs | Aggregate fold results only; repeated order/fee dictionary keys; research period already inspected |
| `research/long_history.py` | Frozen 60/20/20 experiment, 48-hour embargo, legacy replay parity | Existing internal NAV curve is not exported; test partition explicitly unsealed |
| `research/evidence_gate.py` | Rejects unsupported reports; conservative summary | Different report schema from new OOS screening module |
| `research/strategy_evidence_bridge.py` (PR #15) | Rejects incomplete, unsealed and aggregate-only evidence | Flags are caller assertions, not authenticated attestations |

## Implemented in this branch

`research/chronological_evidence.py` exports a timestamped net modelled NAV series, per-period returns, fold ID, modelled order ledger, cost assumptions, data SHA-256, optional declared code revision, and canonical evidence SHA-256. It reconstructs NAV from replay orders and checks final NAV parity against the existing engine. No new strategy, live execution, or historical performance claims.

**Important limitations:** Synthetic unit fixtures do not authenticate market prices; the evidence hash detects content changes but is not a signed independent attestation. Report `holdout_independently_sealed=False` remains mandatory. The exporter is callable from research code but is **not yet wired to the production research CLI**, and does not automatically establish fold independence. Real-market exports and replay verification are future tasks. Existing summary-only outputs must remain insufficient for statistical promotion.

## Next engineering gate

Review CI, compare reconstructed NAV against the long-history NAV path on shared fixtures, wire explicit CLI output to a non-overwriting file, enforce a stable schema, then independently replay the previously rejected BTC/ETH/SOL experiments. Do not merge without review. No strategy may be called validated or profitable.
