"""Android/Codespaces-friendly offline research CLI. No external services or secrets."""

import argparse
import json
from pathlib import Path
from decimal import Decimal
from alpha_lab.data.csv_import import load_csv
from alpha_lab.research.metrics import evaluate
from alpha_lab.research.evidence_gate import summarise_offline_research


def main():
    parser = argparse.ArgumentParser(
        description="Alpha Labs offline research baseline — not trading advice"
    )
    parser.add_argument(
        "csv", help="OHLCV file with ISO-8601 UTC timestamp,open,high,low,close,volume"
    )
    parser.add_argument("--quote", required=True, help="USD, USDC, AUD, USDT, or EUR")
    parser.add_argument(
        "--minutes", type=int, default=60, help="Strict candle interval in minutes"
    )
    parser.add_argument("--provenance", default="user-supplied-unverified")
    parser.add_argument("--fast", type=int, default=12)
    parser.add_argument("--slow", type=int, default=48)
    parser.add_argument("--fee-bps", default="10")
    parser.add_argument("--slippage-bps", default="10")
    parser.add_argument("--allocation", default="0.20")
    parser.add_argument("--capital", default="10000")
    parser.add_argument("--output", default="research-output.json")
    parser.add_argument(
        "--evidence-output",
        default=None,
        help="Optional separate unvalidated evidence summary JSON",
    )
    args = parser.parse_args()
    dataset = load_csv(
        args.csv,
        quote_currency=args.quote,
        interval_minutes=args.minutes,
        provenance=args.provenance,
    )
    result = evaluate(
        dataset,
        fast=args.fast,
        slow=args.slow,
        starting_balance=Decimal(args.capital),
        max_allocation=Decimal(args.allocation),
        fee_bps=Decimal(args.fee_bps),
        slippage_bps=Decimal(args.slippage_bps),
    )
    outfile = Path(args.output)
    if outfile.resolve() == Path(args.csv).resolve():
        parser.error("--output cannot overwrite the source CSV")
    if args.evidence_output is not None and Path(args.evidence_output).resolve() in {
        outfile.resolve(),
        Path(args.csv).resolve(),
    }:
        parser.error("--evidence-output cannot overwrite the source CSV or main report")
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.evidence_output is not None:
        evidence = summarise_offline_research(result)
        evidence_path = Path(args.evidence_output)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Evidence: {evidence_path} | RESEARCH ONLY, NOT VALIDATED ALPHA")
    for period, record in result["periods"].items():
        print(
            f"{period}: strategy {record['strategy']['return_pct']:.3f}% | passive {record['equal_allocation_buy_hold']['return_pct']:.3f}% | double costs {record['double_cost_strategy']['return_pct']:.3f}%"
        )
    print(
        f"Saved: {outfile} | Source: {args.provenance} | This does NOT demonstrate live profitability."
    )


if __name__ == "__main__":
    main()
