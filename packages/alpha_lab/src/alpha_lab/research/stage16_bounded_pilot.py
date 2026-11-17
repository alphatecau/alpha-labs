"""Stage 16 bounded, isolated research pilot: periodic quote checks and disposable fills.

This is a sequential integration pilot, NOT a continuously armed trading engine.
No broker order API, credentials, existing journals, or live execution are used.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from datetime import datetime, timezone

from alpha_lab.research.stage11_coinbase_soak import observe
from alpha_lab.research.stage9_coinbase_paper_rehearsal import rehearse


def pilot(*, cycles=4, observe_fn=observe, rehearse_fn=rehearse):
    if type(cycles) is not int or not 1 <= cycles <= 24:
        raise ValueError("cycles must be 1..24")
    results = []
    for index in range(cycles):
        item = {"cycle": index + 1}
        try:
            quotes = observe_fn(duration_seconds=30, interval_seconds=5)
            item["quotes"] = quotes
            if (quotes.get("status") != "PASS" or quotes.get("mode") != "READ_ONLY"
                    or quotes.get("paper_orders") != 0 or quotes.get("live_orders") != 0
                    or quotes.get("live_execution_authorised") is not False):
                raise ValueError("HALT: quote validation failed")
            paper = rehearse_fn()
            item["paper"] = paper
            if (paper.get("status") != "PASS" or paper.get("mode") != "SIMULATION_ONLY"
                    or paper.get("fills") != 1 or paper.get("backup") != "VERIFIED"
                    or paper.get("restart") != "HALT"
                    or paper.get("live_execution_authorised") is not False):
                raise ValueError("HALT: paper recovery validation failed")
            item["status"] = "PASS"
        except Exception as exc:
            item["status"] = "HALT"
            item["error_type"] = type(exc).__name__
            results.append(item)
            break
        results.append(item)
    passed = len(results) == cycles and all(r["status"] == "PASS" for r in results)
    return {"stage": 16, "mode": "SEQUENTIAL_ISOLATED_RESEARCH",
            "status": "PASS" if passed else "HALT",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "cycles_requested": cycles, "cycles_completed": len(results),
            "results": results, "live_execution_authorised": False,
            "limitation": "Not a continuously armed multi-asset paper runtime"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--approve-synthetic-only", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.approve_synthetic_only:
        parser.error("explicit synthetic-only consent required")
    output = pathlib.Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        result = pilot(cycles=args.cycles)
        result["commit_sha"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip()
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
        print(json.dumps({"status": result["status"], "cycles_completed": result["cycles_completed"],
                          "evidence": str(output), "live_execution_authorised": False}))
        return 0 if result["status"] == "PASS" else 1
    except BaseException:
        os.close(fd)
        raise


if __name__ == "__main__":
    sys.exit(main())
