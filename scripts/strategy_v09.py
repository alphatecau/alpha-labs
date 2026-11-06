#!/usr/bin/env python3
"""Evaluate the frozen, offline Alpha Labs v0.9 historical experiment."""
import argparse
from pathlib import Path

from alpha_lab.research.spot_reference import ReferenceAudit
from alpha_lab.research.strategy_v09 import run_study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify", action="store_true", help="Run separate signal and ledger implementations")
    args = parser.parse_args()
    audit = ReferenceAudit() if args.verify else None
    try:
        decisions = run_study(args.data_root, args.output_dir, Path(__file__).resolve().parents[1], audit)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Strategy Research v0.9 stopped: {exc}\n")
    for variant, result in decisions.items():
        print(f"{variant} ({result['role']}): {result['programme_decision']}")
    if audit:
        print(audit.summary())
    print(f"Previously examined historical data | {args.output_dir}")


if __name__ == "__main__":
    main()
