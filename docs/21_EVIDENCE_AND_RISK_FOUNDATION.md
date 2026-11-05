# Alpha Labs — Evidence and risk foundation (research only)

**Status: locally tested patch, not deployed.** These changes do **not** add a historical data provider, certify profitable strategies, connect an exchange, implement a paper broker or enable trading. Existing v0.6 user-interface and legacy research tools remain untouched.

## What changes

1. `alpha_lab.data.manifests` creates deterministic manifests for strict OHLCV CSV files. Verification checks source-file SHA-256, dataset structure, source metadata, observed timestamps and a metadata checksum. All authenticity and trading flags remain `false`. A self-consistent manifest is **not independently authenticated**; an attacker could rewrite the CSV and recompute checksums. For authentic provenance, pin trusted hashes and source records outside the dataset storage boundary.
2. `alpha_lab.risk.policy` introduces pure offline research-proposal validation: long-only, positive equity, per-position and aggregate exposure thresholds, stale or unverified data, latched-kill-switch *input*, daily realised loss and drawdown. All outcomes have `execution_authorised=false`, including the passing research state. No event-source, broker wiring, persistent kill switch, risk-accounting reconciliation or automated enforcement exists yet.
3. `alpha_lab.research.evidence_gate` summarises existing simulated strategy, equal-allocation passive and double-cost returns. It expressly marks source prices, holdout sealing, observed fills and operating expenses as **unverified or absent**. It cannot issue a profitable-alpha verdict.
4. The existing `alpha_lab.cli` accepts optional `--evidence-output` to save a separate research-only, labelled JSON record. Existing CLI behaviour without that option is preserved. It prevents overwriting its input CSV or output file via the new argument.
5. Three dedicated test files exercise positive and negative cases. Existing research/site CI discovery should pick up these `test_*.py` files once the patch is applied.

## Research report — example (no exchange account)

```sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.cli \
  examples/SYNTHETIC_SOLUSDC_1h.csv --quote USDC --provenance synthetic \
  --output /tmp/alpha-report.json --evidence-output /tmp/alpha-evidence.json
```

Both files contain **fictional/hypothetical** performance. A profitable simulation is never a promotion gate.

## Dataset manifest — example

Provide the **actual** source, instrument and UTC retrieval timestamp. Example timestamp below is illustrative; replace it with the real retrieval record when using real observations.

```sh
PYTHONPATH=packages/alpha_lab/src python -m alpha_lab.data.manifests \
  examples/SYNTHETIC_SOLUSDC_1h.csv \
  --quote USDC --minutes 60 --source-class synthetic \
  --source-id alpha-demo --venue offline --instrument SOL/USDC \
  --retrieved-at-utc 2030-01-01T00:00:00Z \
  --output /tmp/alpha-synthetic.manifest.json
```

The importer rejects missing periods, malformed candles and unfinished terminal intervals relative to the declared retrieval time. The `retrieved_at` field is declared by the operator; the code does not independently authenticate a data provider or clock.

## Research proposal check — example

```python
from decimal import Decimal
from alpha_lab.risk.policy import ResearchProposal, assess_proposal

result = assess_proposal(ResearchProposal(
    equity=Decimal('10000'), open_exposure=Decimal('0'),
    proposed_notional=Decimal('1000'), realised_daily_pnl=Decimal('0'),
    drawdown_fraction=Decimal('0'), quote_age_seconds=10,
    data_integrity_ok=True, kill_switch_active=False, side='LONG',
))
assert result.passes_research_checks
assert result.execution_authorised is False
```

Default limits (illustrative **research** thresholds, not approved risk budgets): 20% new position, 30% aggregate exposure, 2% daily realised loss, 5% drawdown and 180-second quote age. Limits require separate economic and operational approval before they could support paper execution. This module does not verify that input observations themselves are true.

## Local tests

```sh
PYTHONPATH=packages/alpha_lab/src python -m unittest discover -s tests/unit -p 'test_*.py' -v
node --test apps/sites/tests/*.test.cjs
```

## Unresolved production gates

- Trusted multi-year BTC, ETH and SOL historical feed and source reconciliation.
- Immutable *externally pinned* research specification, selection registry and untouched final test data.
- Exchange-calibrated variable fee, spread, liquidity, partial-fill and latency models.
- Exposure-normalised and risk-adjusted benchmarks; multiple-testing controls and statistical confidence intervals.
- Persistent event-sourced independent risk veto and accounting reconciliation.
- Cloud paper broker, forward evaluation, broker security, Australian legal/tax review and explicit live-capital approval.

**No real orders, private keys, exchange credentials or AI inference are added by this patch.**
