"""Research-only comparison on explicitly supplied development CSV. Refuses reserved holdout."""
import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from alpha_lab.data.csv_import import load_csv
from alpha_lab.research.strategies.momentum import ema_signal
from alpha_lab.research.strategies.regime_r1 import r1_signal
from alpha_lab.backtest.costs import CostModel
from alpha_lab.backtest.engine import replay

RESERVED_START = datetime(2027, 1, 1, tzinfo=timezone.utc)
RESERVED_END = datetime(2028, 1, 1, tzinfo=timezone.utc)

def compare(path, quote, provenance):
    dataset = load_csv(path, quote_currency=quote, provenance=provenance)
    bars = dataset.bars
    if any(RESERVED_START <= b.time < RESERVED_END for b in bars):
        raise ValueError("reserved prospective holdout cannot be accessed")
    # Development-only: first 70% for training, final 30% descriptive unsealed.
    split = int(len(bars) * Decimal("0.70"))
    folds = {"development_training": (769, split), "development_unsealed": (split, len(bars))}
    if split <= 769:
        raise ValueError("insufficient training after R1 warmup")
    closes = [b.close for b in bars]
    candidates = {"EMA_12_48_FROZEN": ema_signal(closes), "R1_PREREGISTERED": r1_signal(closes)}
    out = {"dataset_sha256": dataset.sha256, "quote": dataset.quote_currency, "provenance_unverified": provenance,
           "independently_sealed": False, "candidate_profitability_verified": False, "folds": {}}
    for fold, (start, end) in folds.items():
        out["folds"][fold] = {}
        for costs_name, costs in [("reference", CostModel()), ("double_cost", CostModel().twice())]:
            scores = {}
            for name, signal in candidates.items():
                result = replay(bars, signal, start, end, costs=costs)
                scores[name] = {"pnl_quote": result.pnl, "return_pct": result.return_pct,
                                "fees_quote": result.total_modelled_fees,
                                "orders": result.executed_orders, "drawdown_pct": result.max_drawdown_pct}
            passive = replay(bars, candidates["EMA_12_48_FROZEN"], start, end, costs=costs, passive=True)
            scores["PASSIVE_MATCHED_ALLOCATION"] = {"pnl_quote": passive.pnl, "return_pct": passive.return_pct}
            scores["R1_minus_EMA_percentage_points"] = scores["R1_PREREGISTERED"]["return_pct"] - scores["EMA_12_48_FROZEN"]["return_pct"]
            out["folds"][fold][costs_name] = scores
    return out

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--quote", required=True)
    p.add_argument("--provenance", default="unverified-user-csv")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    output = Path(a.output)
    if output.resolve() == Path(a.csv).resolve():
        p.error("cannot overwrite input")
    report = compare(a.csv, a.quote, a.provenance)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
