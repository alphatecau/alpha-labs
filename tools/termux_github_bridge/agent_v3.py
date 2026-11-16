"""Termux v0.3 supervised polling controller.

This controller intentionally delegates only to the restricted v0.2 worker.
It does not accept remote shell commands, install packages or elevate permissions.
"""
import argparse
import os
import pathlib
import signal
import subprocess
import sys
import time

MIN_INTERVAL = 60
MAX_INTERVAL = 3600

def validate_interval(value):
    interval = int(value)
    if not MIN_INTERVAL <= interval <= MAX_INTERVAL:
        raise ValueError("interval must be 60..3600 seconds")
    return interval

def worker_path():
    path = pathlib.Path(__file__).resolve().parent / "worker_v2.py"
    if not path.is_file():
        raise FileNotFoundError("worker_v2.py missing beside controller")
    return path

def run_once(path, execute):
    argv = [sys.executable, str(path)]
    if execute:
        argv.append("--execute")
    return subprocess.run(argv, timeout=90, check=False).returncode

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=validate_interval, default=120)
    parser.add_argument("--execute", action="store_true",
                        help="Process only v0.2 allowlisted tasks")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    path = worker_path()
    stop = False
    def shutdown(_signal, _frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    while not stop:
        try:
            code = run_once(path, args.execute)
            if code:
                print("Worker returned non-zero; retry on next interval", flush=True)
        except subprocess.TimeoutExpired:
            print("Worker timed out; retry on next interval", flush=True)
        if args.once:
            break
        deadline = time.monotonic() + args.interval
        while not stop and time.monotonic() < deadline:
            time.sleep(min(1, max(0, deadline-time.monotonic())))

if __name__ == "__main__":
    main()
