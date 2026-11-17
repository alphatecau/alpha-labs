"""Stage 13 read-only evidence collector. No order submission, broker credentials or journal writes."""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys

SUITES = (
    "test_stage10_coinbase_paper_reliability.py",
    "test_paper_commit_boundaries.py",
    "test_paper_fill_backup_recovery_stage8.py",
    "test_paper_journal_writer_lock.py",
    "test_local_paper_recovery.py",
    "test_live_paper_bridge.py",
    "test_paper_safety.py",
    "test_coinbase_research_paper_isolation.py",
)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New JSON evidence file (never overwritten)")
    args = parser.parse_args()
    output = pathlib.Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    root = pathlib.Path(__file__).resolve().parents[1]
    source = root / "packages" / "alpha_lab" / "src"
    env = dict(os.environ, PYTHONPATH=str(source) + os.pathsep + str(root))
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    clean = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout == ""
    results = []
    try:
        for suite in SUITES:
            command = [sys.executable, "-m", "unittest", "discover", "-s", "tests/unit", "-p", suite, "-v"]
            proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=180)
            combined = (proc.stdout + "\n" + proc.stderr).encode()
            results.append({"suite": suite, "passed": proc.returncode == 0,
                            "returncode": proc.returncode, "output_sha256": hashlib.sha256(combined).hexdigest(),
                            "output_tail": (proc.stdout + "\n" + proc.stderr)[-1800:]})
            if proc.returncode:
                break
        passed = len(results) == len(SUITES) and all(x["passed"] for x in results)
        evidence = {"stage": 13, "mode": "OFFLINE_READ_ONLY_TESTS", "status": "PASS" if passed else "FAIL",
                    "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "commit_sha": sha,
                    "checkout_clean_at_start": clean, "python": sys.version.split()[0],
                    "suites": results, "paper_orders_placed_by_collector": 0,
                    "live_orders_placed_by_collector": 0, "live_execution_authorised": False,
                    "scope_limit": "Does not prove an extended paper pilot, independent review or deployed-site acceptance"}
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(evidence, handle, indent=2)
            handle.write("\n")
        print(json.dumps({"status": evidence["status"], "commit_sha": sha,
                          "suites_passed": sum(x["passed"] for x in results),
                          "suites_total": len(SUITES), "evidence": str(output)}))
        return 0 if passed else 1
    except BaseException:
        os.close(fd)
        raise

if __name__ == "__main__":
    sys.exit(main())
