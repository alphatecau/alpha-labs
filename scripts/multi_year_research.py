#!/usr/bin/env python3
"""Standard-library only research pipeline. Nothing here executes trades."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from alpha_lab.data.adapters.binance_archive import SYMBOLS, build_dataset, verify_dataset
from alpha_lab.research.long_history import freeze_experiment, evaluate_spec, default_config, _config


def paths(root: Path, symbol: str, start: str, end: str) -> tuple[Path, Path, Path, Path]:
    csv_path = root / "curated" / "binance-vision" / f"{symbol}-1h-{start}_to_{end}.csv"
    manifest = csv_path.with_suffix(".manifest.json")
    specs = root / "replay" / "experiments" / f"{symbol}-1h-{start}_to_{end}.frozen.json"
    report = root / "replay" / "reports" / f"{symbol}-1h-{start}_to_{end}.report.json"
    return csv_path, manifest, specs, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Alpha Labs multi-year spot research (never sends orders)")
    parser.add_argument("mode", choices=("fetch", "freeze", "evaluate", "run", "verify"))
    parser.add_argument("--symbols", nargs="+", choices=SYMBOLS, default=list(SYMBOLS))
    parser.add_argument("--from-month", dest="start", default="2023-01")
    parser.add_argument("--through-month", dest="end", default="2025-12")
    parser.add_argument("--data-root", type=Path, default=Path("datasets"))
    parser.add_argument("--annual-overhead-usdt", default="0",
                        help="Modelled overhead per market/year in USDT, default 0 (NOT a cost claim)")
    args = parser.parse_args()
    config = default_config()
    config["operating_cost_usdt_per_year"] = args.annual_overhead_usdt
    _config(config)
    # Validate before any network writes.
    from alpha_lab.data.adapters.binance_archive import month_range
    month_range(args.start, args.end)
    for symbol in args.symbols:
        csv_path, manifest, frozen, report = paths(args.data_root, symbol, args.start, args.end)
        if args.mode in ("fetch", "run"):
            print(f"FETCH {symbol} {args.start}..{args.end}: checksum-verified monthly spot archives", flush=True)
            result = build_dataset(symbol, args.start, args.end, args.data_root)
            print(f"FETCH PASS: {result['bars']} complete hourly candles; SHA256={result['sha256']}")
        if args.mode == "verify":
            print(f"VERIFY {symbol}: {verify_dataset(csv_path, manifest)['csv_sha256']}")
        if args.mode in ("freeze", "run"):
            spec = freeze_experiment(csv_path, manifest, frozen, config)
            print(f"FREEZE {symbol}: {spec['specification_sha256']} (NOT a sealed holdout)")
        if args.mode in ("evaluate", "run"):
            result = evaluate_spec(csv_path, manifest, frozen, report)
            print(f"EVALUATE {symbol}: {report}")
            for name, metrics in result["periods"].items():
                print(f"  {name}: strategy={metrics['modelled_strategy']['net_modelled_execution_return_pct']:.3f}% "
                      f"passive={metrics['matched_initial_allocation_passive']['net_modelled_execution_return_pct']:.3f}% "
                      f"2x-cost={metrics['strategy_double_execution_friction']['net_modelled_execution_return_pct']:.3f}%")
            print("WARNING: UNSEALED historical evaluation, assumed fills; no validated alpha or trading authorization")


if __name__ == "__main__":
    main()
