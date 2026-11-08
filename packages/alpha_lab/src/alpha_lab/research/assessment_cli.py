"""Offline assessment CLI for chronological research evidence files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from alpha_lab.research.evidence_assessment import assess_evidence

def run_assessment(files: list[str | Path], output: str | Path, *,
                   additional_cost_per_period: float) -> dict:
    target = Path(output)
    sources = [Path(x) for x in files]
    if not sources:
        raise ValueError("At least one evidence file required")
    if target.resolve() in [p.resolve() for p in sources]:
        raise ValueError("Output cannot overwrite evidence input")
    if target.exists():
        raise FileExistsError("Refusing to overwrite assessment")
    folds = [json.loads(p.read_text(encoding="utf-8")) for p in sources]
    report = assess_evidence(folds, additional_cost_per_period=additional_cost_per_period)
    report["evidence_file_count"] = len(sources)
    report["research_only"] = True
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    return report

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research-only, fail-closed evidence assessment")
    parser.add_argument("evidence", nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--additional-cost-per-period", required=True, type=float)
    args = parser.parse_args(argv)
    report = run_assessment(args.evidence, args.output,
                            additional_cost_per_period=args.additional_cost_per_period)
    print(report["status"] + ": " + ", ".join(report["reasons"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
