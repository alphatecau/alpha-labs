# Alpha Labs PR #15 — five-task engineering acceptance report

Status: **research-only, draft, no live trading**.

## 1. CI verification
The earlier revision `2f81689` passed both GitHub Actions workflows, including 129 Python unit tests. The new commits on this branch require their **own** CI confirmation; earlier green runs do not certify later changes.

## 2. Accounting reconciliation
Added `research/accounting_reconciliation.py`, which independently recomputes each hourly modelled NAV and net return from original OHLCV, prior-close EMA signals, and the cost model. It verifies timestamps, final NAV and closed trade counts. Tests reject tampered NAV, tampered returns and mismatched datasets. This is independent *code-path* accounting reconciliation, **not** independent market-data authentication or a real fill audit.

## 3. BTC/ETH/SOL historical replay
Existing `research/evidence_export.py` already supports source-archive checksum verification, stored-vs-recomputed research report parity and reproducible BTCUSDT/ETHUSDT/SOLUSDT evidence bundles. Existing documentation records an April 2023–December 2025 historical window and prior rejected EMA results. **No new real-market replay was executed in this PR** because the raw Binance archives and curated datasets are not committed to GitHub and are not accessible through the connected repository tools. Do not claim this task completed.

To run on a network-connected machine with sufficient disk space:

```sh
export PYTHONPATH=packages/alpha_lab/src
python scripts/multi_year_research.py fetch --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12
python scripts/multi_year_research.py freeze --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12
python scripts/multi_year_research.py evaluate --symbols BTCUSDT ETHUSDT SOLUSDT --from-month 2023-04 --through-month 2025-12
```

**Caution:** These historical partitions have been inspected; they are not sealed holdouts. The archive checksums authenticate provider bytes, not prices independently.

## 4. Statistical evidence screening
`research/evidence_assessment.py` checks fold schemas, evidence SHA-256, consistent data/code revisions, non-overlapping windows, period NAV-return consistency, and applies `strategy_evidence.evaluate_oos` with a user-specified additional cost stress. The resulting overall status remains `INSUFFICIENT_EVIDENCE` because independent holdout and executable fill evidence are absent. Fold summaries are never treated as an independent final validation.

## 5. Automated reporting
`research/assessment_cli.py` writes a non-overwriting JSON assessment:

```sh
python -m alpha_lab.research.assessment_cli evidence-fold-001.json \
  --output assessment.json --additional-cost-per-period 0.0001
```

The cost stress above is an **example assumption**, not a verified trading cost. The CLI never authorises execution. Results may contain diagnostic screen status `REJECT` or `REVIEW_REQUIRED` but the overall status remains `INSUFFICIENT_EVIDENCE`.

## Remaining gates
- Confirm CI on the latest branch head, inspect failed tests and correct if necessary.
- Independently review reconciliation methodology, especially zero-trade, open-position and variable-fee fixtures.
- Obtain and independently verify genuine BTC/ETH/SOL source datasets; replay and archive reports with immutable input and code hashes.
- Review fold independence, statistical multiple-comparison risk, data provenance and modelled cost realism before merging.
- No merge, deployment, agent execution or live trading without explicit approval.
