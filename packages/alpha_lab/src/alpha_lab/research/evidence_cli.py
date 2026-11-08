"""Explicit, non-overwriting CLI for historical modelled evidence exports."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from alpha_lab.data.csv_import import load_csv
from alpha_lab.research.chronological_evidence import export_replay_evidence

def run_export(csv_path: str | Path, output_path: str | Path, *,
               start: int, end: int, fold_id: str,
               provenance: str = "user-supplied-unverified",
               quote: str = "USDT", code_revision: str | None = None) -> dict:
    source = Path(csv_path)
    target = Path(output_path)
    if source.resolve() == target.resolve():
        raise ValueError("Output cannot overwrite input data")
    # Validate target before running expensive research.
    if target.exists():
        raise FileExistsError("Refusing to overwrite existing evidence")
    dataset = load_csv(source, quote_currency=quote,
                       interval_minutes=60, provenance=provenance)
    evidence = export_replay_evidence(dataset, start=start, end=end,
                                      fold_id=fold_id, code_revision=code_revision)
    payload = json.dumps(evidence, sort_keys=True, indent=2, allow_nan=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents clobbering existing evidence even on a race.
    with target.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    return evidence

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline historical modelled evidence only; never live trading")
    parser.add_argument("csv")
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", type=int, required=True, help="Inclusive candle index")
    parser.add_argument("--end", type=int, required=True, help="Exclusive candle index")
    parser.add_argument("--fold-id", required=True)
    parser.add_argument("--provenance", default="user-supplied-unverified")
    parser.add_argument("--quote", default="USDT")
    parser.add_argument("--code-revision")
    args = parser.parse_args(argv)
    evidence = run_export(args.csv, args.output, start=args.start, end=args.end,
                          fold_id=args.fold_id, provenance=args.provenance,
                          quote=args.quote, code_revision=args.code_revision)
    print("RESEARCH_ONLY evidence_sha256=" + evidence["evidence_sha256"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
