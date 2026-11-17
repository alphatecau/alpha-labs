"""Offline Stage 12 acceptance gate for Stage 11 Coinbase soak JSON evidence.

This validates recorded samples, not elapsed wall-clock time or exchange uptime.
No network, account access, execution, or journal writes.
"""
import argparse
import json
from pathlib import Path

PRODUCTS = ("BTC-USD", "ETH-USD", "SOL-USD")


def assess(report, *, min_samples=100, min_availability_pct=99.0):
    failures = []
    if not isinstance(report, dict) or report.get("mode") != "READ_ONLY":
        return {"accepted": False, "reasons": ["missing READ_ONLY report"]}
    if report.get("live_execution_authorised") is not False:
        failures.append("live execution boundary missing")
    if report.get("paper_orders") != 0 or report.get("live_orders") != 0:
        failures.append("nonzero or unknown orders")
    samples = report.get("samples")
    if type(samples) is not int or samples < min_samples:
        failures.append("insufficient samples")
    if report.get("status") != "PASS":
        failures.append("soak reported DEGRADED or unknown")
    products = report.get("products")
    if not isinstance(products, dict) or set(products) != set(PRODUCTS):
        failures.append("missing or unexpected products")
    else:
        for product in PRODUCTS:
            entry = products[product]
            if not isinstance(entry, dict):
                failures.append(f"{product}: invalid metrics")
                continue
            healthy, unverified, availability, age = (
                entry.get("healthy"), entry.get("unverified"),
                entry.get("availability_pct"), entry.get("max_exchange_age_seconds")
            )
            if (type(healthy) is not int or type(unverified) is not int
                    or type(samples) is not int or healthy < 0 or unverified < 0
                    or healthy + unverified != samples):
                failures.append(f"{product}: inconsistent sample counts")
            if (type(availability) not in (int, float) or not 0 <= availability <= 100
                    or type(samples) is not int or samples <= 0
                    or type(healthy) is not int
                    or abs(availability - round(100 * healthy / samples, 2)) > 0.01
                    or availability < min_availability_pct):
                failures.append(f"{product}: availability below threshold or inconsistent")
            if type(age) not in (int, float) or not 0 <= age <= 10:
                failures.append(f"{product}: invalid or stale maximum exchange age")
    return {"accepted": not failures, "reasons": failures,
            "scope": "SAMPLE_METRICS_ONLY",
            "elapsed_wall_clock_verified": False,
            "production_trading_authorised": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = assess(json.loads(args.report.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
