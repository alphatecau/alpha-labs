#!/usr/bin/env python3
"""Package existing research for independent review; no downloads or trades."""
import argparse
import json
from pathlib import Path

from alpha_lab.data.adapters.binance_archive import SYMBOLS
from alpha_lab.research.evidence_export import export_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("datasets"))
    parser.add_argument("--symbols", nargs="+", choices=SYMBOLS, default=list(SYMBOLS))
    parser.add_argument("--from-month", default="2023-04")
    parser.add_argument("--through-month", default="2025-12")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export_evidence(args.data_root, args.symbols, args.from_month, args.through_month, args.output)
    print(json.dumps(result, indent=2))
    print("Local reports reproduced. Independent source/price review remains outstanding; trading disabled.")


if __name__ == "__main__":
    main()
