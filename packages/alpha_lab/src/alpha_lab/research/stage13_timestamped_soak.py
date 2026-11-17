"""Stage 13: bounded, timestamped Coinbase public-feed evidence capture.

Monotonic elapsed time is measured locally; it is not remote attestation.
No execution imports, authenticated endpoints or persistent journal changes.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from alpha_lab.research.stage11_coinbase_soak import observe


def capture(*, duration_seconds=1800, interval_seconds=15,
            clock=lambda: datetime.now(timezone.utc),
            monotonic=time.monotonic, sleep=time.sleep, feed=None):
    if not 30 <= duration_seconds <= 7200 or not 2 <= interval_seconds <= 120:
        raise ValueError("HALT: invalid bounded soak configuration")
    start_utc = clock()
    start_tick = monotonic()
    if start_utc.tzinfo is None or start_utc.utcoffset().total_seconds() != 0:
        raise ValueError("HALT: UTC clock required")
    result = observe(duration_seconds=duration_seconds, interval_seconds=interval_seconds,
                     feed=feed, clock=clock, monotonic=monotonic, sleep=sleep)
    elapsed = monotonic() - start_tick
    finish_utc = clock()
    if finish_utc.tzinfo is None or finish_utc.utcoffset().total_seconds() != 0:
        raise ValueError("HALT: UTC clock required")
    result.update({"started_at_utc": start_utc.isoformat(),
                   "finished_at_utc": finish_utc.isoformat(),
                   "elapsed_monotonic_seconds": round(elapsed, 3),
                   "duration_verified_locally": elapsed >= duration_seconds,
                   "independent_time_attestation": False})
    if elapsed < duration_seconds:
        result["status"] = "INCOMPLETE"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=int, default=1800)
    parser.add_argument("--interval-seconds", type=int, default=15)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = capture(duration_seconds=args.duration_seconds,
                     interval_seconds=args.interval_seconds)
    report = json.dumps(result, indent=2)
    if args.output is not None:
        # Refuse to overwrite prior evidence.
        with args.output.open("x", encoding="utf-8") as output:
            output.write(report + "\n")
    print(report)
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
