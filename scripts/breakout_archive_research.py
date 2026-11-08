#!/usr/bin/env python3
"""Research-only, archive-verified breakout cost-stress runner.

Uses existing checksum-verified Binance Vision curated datasets. Does not
download, trade, tune parameters, approve strategies or claim profitability.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from alpha_lab.data.adapters.binance_archive import SYMBOLS, verify_dataset
from alpha_lab.research.breakout_evaluation import evaluate_breakout_csv

def main() -> None:
    parser = argparse.ArgumentParser(description="Verified offline breakout diagnostic; trading disabled")
    parser.add_argument("--data-root", type=Path, default=Path("datasets"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--from-month", default="2023-04")
    parser.add_argument("--through-month", default="2025-12")
    parser.add_argument("--start-index", type=int, required=True)
    parser.add_argument("--end-index", type=int, required=True)
    parser.add_argument("--symbols", nargs="+", choices=SYMBOLS, default=list(SYMBOLS))
    args = parser.parse_args()
    if len(set(args.symbols)) != len(args.symbols):
        parser.error("Duplicate market symbol")
    if args.start_index < 840 or args.end_index <= args.start_index:
        parser.error("Invalid warmup or evaluation window")
    # Preflight all inputs before creating any outputs.
    items = []
    for symbol in args.symbols:
        name = f"{symbol}-1h-{args.from_month}_to_{args.through_month}"
        source = args.data_root/"curated"/"binance-vision"/f"{name}.csv"
        manifest = source.with_suffix(".manifest.json")
        verified = verify_dataset(source, manifest)
        if args.end_index > verified["candle_count"]:
            parser.error(f"Evaluation end exceeds verified history: {symbol}")
        items.append((symbol, source, manifest))
    outputs = [(symbol, fee, slip, args.output_root/f"{symbol}-breakout-{fee}bps-fee-{slip}bps-slip.json")
               for symbol, _, _ in items for fee, slip in ((10, 10), (20, 20), (40, 40))]
    if len({p.resolve() for _, _, _, p in outputs}) != len(outputs):
        parser.error("Duplicate output paths")
    if any(p.exists() for _, _, _, p in outputs):
        parser.error("Output already exists: use a fresh output directory")
    for symbol, source, manifest in items:
        for fee, slip in ((10, 10), (20, 20), (40, 40)):
            output = args.output_root/f"{symbol}-breakout-{fee}bps-fee-{slip}bps-slip.json"
            report = evaluate_breakout_csv(
                source, output, provenance="binance-vision-spot-monthly-verified-archive-digest",
                manifest_path=manifest, start=args.start_index, end=args.end_index,
                fee_bps=str(fee), slippage_bps=str(slip))
            print(f"{symbol} {fee}/{slip} bps: {report['status']}; "
                  f"legacy_candidate_return={report['candidate']['return_pct']:.4f}%; "
                  f"risk_candidate_return={report['risk_constrained_candidate']['return_pct']:.4f}%; "
                  f"risk_reconciliation={report['risk_constrained_reconciliation']['status']}; "
                  f"passive_return={report['passive_comparator']['return_pct']:.4f}%; "
                  "portfolio_cross_asset_risk=UNVERIFIED; no profitable-edge claim")
    print("RESEARCH ONLY: no sealed holdout, no executable quotes, no risk authorisation")

if __name__ == "__main__":
    main()
