#!/usr/bin/env python3
"""Evaluate the single registered Alpha Labs v0.8 historical experiment."""
import argparse
from pathlib import Path

from alpha_lab.research.strategy_v08 import run_study


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("datasets"),
                        help="Root containing the audited raw archives and curated CSVs")
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/replay/strategy-v0.8"),
                        help="New directory for the three comparison reports")
    args = parser.parse_args()
    registry = Path(__file__).resolve().parents[1] / "configs" / "strategy-v0.8.json"
    try:
        decision = run_study(args.data_root, args.output_dir, registry)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Strategy Research v0.8 stopped: {exc}\n")
    print(f"{decision} | Previously examined historical data | Reports: {args.output_dir}")


if __name__ == "__main__":
    main()
