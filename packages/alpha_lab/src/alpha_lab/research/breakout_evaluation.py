"""Offline breakout candidate evaluation. No trading, no promotion decisions."""
from __future__ import annotations
from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path
from alpha_lab.data.csv_import import load_csv
from alpha_lab.backtest.engine import replay
from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.breakout_candidate import breakout_signals
from alpha_lab.data.adapters.binance_archive import verify_dataset

def evaluate_breakout_csv(source: str | Path, output: str | Path, *,
                          provenance: str, start: int, end: int,
                          fee_bps: str = "10", slippage_bps: str = "10",
                          manifest_path: str | Path | None = None) -> dict:
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError("Output must be a new path distinct from input")
    if not provenance.strip() or provenance == "user-supplied-unverified":
        raise ValueError("Explicit data provenance required")
    # Free-text provenance is not proof of archive verification.
    synthetic = provenance == "synthetic-test-fixture"
    if not synthetic and manifest_path is None:
        raise ValueError("Verified Binance archive manifest required for non-synthetic research")
    verified_manifest = None
    if manifest_path is not None:
        verified_manifest = verify_dataset(source, Path(manifest_path))
        if synthetic:
            raise ValueError("Synthetic provenance cannot claim verified market archives")
        if provenance != "binance-vision-spot-monthly-verified-archive-digest":
            raise ValueError("Provenance must match verified Binance archive")
    data = load_csv(source, quote_currency="USDT", interval_minutes=60,
                    provenance=provenance)
    if not (0 <= start < end <= len(data.bars)) or start < 840:
        raise ValueError("Insufficient warmup or invalid evaluation window")
    try:
        fees, slippage = Decimal(fee_bps), Decimal(slippage_bps)
    except (ValueError, ArithmeticError) as exc:
        raise ValueError("Invalid cost assumptions") from exc
    if not all(x.is_finite() and 0 <= x <= 1000 for x in (fees, slippage)):
        raise ValueError("Invalid cost assumptions")
    signals = breakout_signals(data.bars)
    model = CostModel(fee_bps=fees, adverse_slippage_bps=slippage)
    candidate = replay(data.bars, signals, start, end, costs=model)
    passive = replay(data.bars, signals, start, end, costs=model, passive=True)
    result = {
        "schema": "alpha-labs.breakout-candidate-offline.v1",
        "dataset_sha256": data.sha256,
        "provenance_declared": provenance,
        "source_archive_manifest_verified": verified_manifest is not None,
        "synthetic_fixture": synthetic,
        "independent_price_authentication_performed": False,
        "risk_policy_enforced_by_replay": False,
        "strategy_candidate_status": "NOT_ELIGIBLE_FOR_PROMOTION",
        "quote_currency": data.quote_currency,
        "window_start": start,
        "window_end_exclusive": end,
        "fee_bps_each_side_assumed": str(fees),
        "slippage_bps_each_side_assumed": str(slippage),
        "candidate": asdict(candidate),
        "passive_comparator": asdict(passive),
        "candidate_excess_return_percentage_points": candidate.return_pct-passive.return_pct,
        "modelled_fills_only": True,
        "independently_sealed_holdout": False,
        "profitability_verified": False,
        "promotion_authorised": False,
        "trading_enabled": False,
        "status": "RESEARCH_ONLY_UNVERIFIED",
    }
    payload = json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+"\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    return result
