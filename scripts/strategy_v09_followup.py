#!/usr/bin/env python3
"""Replay the fixed v0.9 cost grid and two exploratory comparisons offline."""
import argparse
from pathlib import Path

from alpha_lab.research.strategy_v09_followup import run_followup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = run_followup(args.data_root, args.output, root)
    for variant, study in report["exploratory"]["results"].items():
        print(f"{variant}: {study['screen']['outcome']}")
    print(f"Research evidence written to {args.output}")


if __name__ == "__main__":
    main()
