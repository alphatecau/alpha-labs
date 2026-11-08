"""Offline assessment CLI for chronological research evidence files."""
from __future__ import annotations
import argparse
import json
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from alpha_lab.research.evidence_assessment import assess_evidence

def run_assessment(files: list[str | Path], output: str | Path, *,
                   additional_cost_per_period: float, tested_strategies: int = 1) -> dict:
    target = Path(output)
    sources = [Path(x) for x in files]
    if not sources:
        raise ValueError("At least one evidence file required")
    if target.resolve() in [p.resolve() for p in sources]:
        raise ValueError("Output cannot overwrite evidence input")
    if target.exists():
        raise FileExistsError("Refusing to overwrite assessment")
    raw = [p.read_bytes() for p in sources]
    folds = [json.loads(payload) for payload in raw]
    report = assess_evidence(folds, additional_cost_per_period=additional_cost_per_period, tested_strategies=tested_strategies)
    report["evidence_file_count"] = len(sources)
    report["research_only"] = True
    report["schema"] = "alpha-labs.offline-assessment.v1"
    report["input_files"] = [
        {"filename": source.name, "sha256": sha256(payload).hexdigest(),
         "bytes": len(payload)}
        for source, payload in zip(sources, raw)
    ]
    report["cost_stress_per_period_assumed"] = additional_cost_per_period
    report["dataset_sha256_declared"] = sorted({
        fold.get("dataset_sha256") for fold in folds
        if isinstance(fold, dict) and isinstance(fold.get("dataset_sha256"), str)
    })
    report["code_revisions_declared"] = sorted({
        fold.get("code_revision_declared") for fold in folds
        if isinstance(fold, dict) and isinstance(fold.get("code_revision_declared"), str)
    })
    report["source_price_independently_authenticated"] = False
    report["strategy_profitable_verified"] = False
    report["archive_provenance_independently_authenticated"] = False
    report["historical_capture_independently_attested"] = False
    report["provenance_gate_status"] = "NOT_INTEGRATED_OR_NOT_INDEPENDENTLY_VERIFIED"
    report["promotion_authorised"] = False
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
    parser.add_argument("--tested-strategies", type=int, default=1,
                        help="Number of strategies examined; does not apply multiplicity correction")
    args = parser.parse_args(argv)
    report = run_assessment(args.evidence, args.output,
                            additional_cost_per_period=args.additional_cost_per_period,
                            tested_strategies=args.tested_strategies)
    print(report["status"] + ": " + ", ".join(report["reasons"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
