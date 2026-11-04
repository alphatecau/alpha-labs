"""Deterministic rolling historical replay; research only."""
import argparse
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from alpha_lab.data.csv_import import load_csv
from alpha_lab.research.strategies.momentum import ema_signal
from alpha_lab.backtest.engine import replay
from alpha_lab.backtest.costs import CostModel


def evaluate_windows(dataset, initial=720, window=168):
    if dataset.interval_minutes != 60:
        raise ValueError("Hourly candles required")
    if initial < 96 or window < 24:
        raise ValueError("Invalid evaluation configuration")
    if len(dataset.bars) < initial + window:
        raise ValueError("Insufficient historical data")

    bars = dataset.bars
    base = CostModel(Decimal("10"), Decimal("10"))
    folds = []

    for start in range(initial, len(bars) - window + 1, window):
        end = start + window

        # Only observations available through this window are used.
        history = bars[:end]
        signals = ema_signal(
            [bar.close for bar in history], 12, 48
        )

        def run(costs, passive=False):
            return replay(
                history, signals, start, end,
                starting_balance=Decimal("10000"),
                max_allocation=Decimal("0.20"),
                costs=costs,
                passive=passive
            )

        strategy = run(base)
        benchmark = run(base, passive=True)
        stress = run(base.twice())

        folds.append({
            "start_utc": bars[start].time.isoformat(),
            "end_exclusive_utc": (
                bars[end - 1].time + timedelta(hours=1)
            ).isoformat(),
            "strategy_pct": strategy.return_pct,
            "passive_pct": benchmark.return_pct,
            "double_cost_pct": stress.return_pct,
            "max_drawdown_pct": strategy.max_drawdown_pct,
        })

    wins = sum(
        fold["strategy_pct"] > fold["passive_pct"]
        for fold in folds
    )

    return {
        "status": "HISTORICAL_REPLAY_NOT_VALIDATED_ALPHA",
        "dataset_sha256": dataset.sha256,
        "quote_currency": dataset.quote_currency,
        "initial_bars": initial,
        "window_bars": window,
        "strategy": "EMA_12_48_FROZEN",
        "folds": folds,
        "outperformance_windows": wins,
        "total_windows": len(folds),
        "trading_enabled": False,
        "limitations": [
            "No optimisation or model retraining",
            "Prior research has inspected this evaluation period",
            "Transaction costs are assumptions, not observed fills",
            "Not an independent profitability validation"
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.csv)
    dataset = load_csv(
        source,
        quote_currency="USDT",
        interval_minutes=60,
        provenance="binance-public-spot-monthly"
    )

    manifest = json.loads(
        source.with_suffix(".manifest.json").read_text()
    )

    if (
        manifest["csv_sha256"] != dataset.sha256
        or manifest["quote_currency"] != "USDT"
        or manifest["interval_minutes"] != 60
        or manifest["candles"] != len(dataset.bars)
    ):
        raise ValueError("Dataset manifest validation failed")

    result = evaluate_windows(dataset)

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")

    print(
        f"PASS: {source.name} | "
        f"{result['outperformance_windows']}/"
        f"{result['total_windows']} windows outperform"
    )


if __name__ == "__main__":
    main()
