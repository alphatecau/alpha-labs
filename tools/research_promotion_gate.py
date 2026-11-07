"""Fail-closed, offline research promotion gate.

This is an evidence completeness gate, not a profitability estimator or
authorisation to trade. No broker, network or execution dependencies.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_EVIDENCE = (
    "point_in_time_data",
    "source_provenance",
    "independent_price_checks",
    "execution_cost_calibration",
    "chronological_out_of_sample",
    "multiple_testing_control",
    "independent_replay",
    "prospective_evaluation",
    "risk_controls",
    "capacity_assessment",
)
REQUIRED_METRICS = (
    "net_return",
    "cost_stress_net_return",
    "max_drawdown",
    "adjusted_lower_bound",
    "closed_trades",
    "positive_forward_folds",
    "total_forward_folds",
)


def evaluate(record: dict) -> dict:
    if type(record) is not dict:
        raise ValueError("Expected a JSON object")
    name = record.get("experiment_id")
    if type(name) is not str or not name.strip():
        raise ValueError("experiment_id must be a nonempty string")
    evidence = record.get("evidence")
    metrics = record.get("metrics")
    if type(evidence) is not dict or type(metrics) is not dict:
        raise ValueError("evidence and metrics must be JSON objects")
    reasons = []
    for key in REQUIRED_EVIDENCE:
        if evidence.get(key) is not True:
            reasons.append(f"missing_or_unverified:{key}")
    for key in REQUIRED_METRICS:
        value = metrics.get(key)
        if type(value) not in (int, float) or not -1e100 < value < 1e100:
            reasons.append(f"missing_or_invalid:{key}")
    # Numeric checks apply only to verified evidence and complete metrics.
    if not reasons:
        if metrics["net_return"] <= 0:
            reasons.append("nonpositive_net_return")
        if metrics["cost_stress_net_return"] <= 0:
            reasons.append("nonpositive_cost_stress_return")
        if metrics["adjusted_lower_bound"] <= 0:
            reasons.append("nonpositive_adjusted_lower_bound")
        if not 0 <= metrics["max_drawdown"] <= 0.05:
            reasons.append("drawdown_outside_research_threshold")
        if metrics["closed_trades"] < 40:
            reasons.append("insufficient_closed_trades")
        total = metrics["total_forward_folds"]
        positive = metrics["positive_forward_folds"]
        if total < 1 or not 0 <= positive <= total or positive / total < 0.6:
            reasons.append("forward_fold_consistency_failed")
    # Never return a live-trading authorisation.
    return {
        "schema": "alpha-labs.research-gate.v1",
        "experiment_id": name,
        "decision": "REJECT" if reasons and all(not r.startswith(("missing_", "missing_or_")) for r in reasons)
                    else ("BLOCKED" if reasons else "ELIGIBLE_FOR_INDEPENDENT_REVIEW"),
        "live_trading_authorised": False,
        "reasons": reasons,
        "note": "Eligibility is not proof of alpha and never authorises execution.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="Research evidence JSON")
    parser.add_argument("--output", type=Path, help="Optional result JSON")
    args = parser.parse_args()
    result = evaluate(json.loads(args.record.read_text(encoding="utf-8")))
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    if result["decision"] != "ELIGIBLE_FOR_INDEPENDENT_REVIEW":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
