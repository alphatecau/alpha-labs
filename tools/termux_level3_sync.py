#!/usr/bin/env python3
"""Level 3 opt-in Git sync adapter. No arbitrary shell, remote approval or trading."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time

SHA = re.compile(r"^[a-f0-9]{40}$")
REPO = "alphatecau/alpha-labs"
EXPIRY_SECONDS = 600

class Refused(Exception):
    pass

def private_file(path):
    if path.is_symlink() or not path.is_file():
        raise Refused("Approval must be a regular file, not a symlink")
    s = path.stat()
    if s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o600:
        raise Refused("Approval ownership or permissions invalid")

def config(path):
    if path.is_symlink():
        raise Refused("Configuration symlink refused")
    data = json.loads(path.read_text())
    if set(data) != {"checkout", "repo"} or data["repo"] != REPO:
        raise Refused("Unsupported configuration")
    checkout = Path(data["checkout"])
    if not checkout.is_absolute() or checkout.is_symlink() or not checkout.is_dir():
        raise Refused("Checkout must be an existing absolute directory, not a symlink")
    checkout = checkout.resolve(strict=True)
    if checkout == Path.home().resolve() or checkout == Path("/"):
        raise Refused("Unsafe checkout")
    return checkout

def run_sync(checkout, action, sha=None):
    script = checkout / "tools" / "termux_approved_sync.py"
    if not script.is_file() or script.is_symlink():
        raise Refused("Approved sync script absent")
    argv = [sys.executable, str(script), action]
    if sha:
        argv += ["--commit", sha]
    if action == "apply":
        argv.append("--approve")
    result = subprocess.run(argv, cwd=checkout, capture_output=True, text=True, timeout=90)
    # Never forward subprocess stderr: it may contain remote URL or sensitive data.
    if result.returncode:
        raise Refused("Approved sync refused or failed; inspect locally")
    return result.stdout[:2048]

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--state-dir", required=True)
    sub = p.add_subparsers(dest="action", required=True)
    for name in ("plan", "authorise", "apply"):
        x = sub.add_parser(name)
        x.add_argument("--commit", required=True)
    sub.add_parser("recover-status")
    args = p.parse_args(argv)
    state = Path(args.state_dir)
    if state.is_symlink() or not state.is_dir() or state.stat().st_uid != os.getuid() or stat.S_IMODE(state.stat().st_mode) != 0o700:
        raise Refused("State directory must be owned by operator with mode 0700")
    checkout = config(Path(args.config))
    approval = state / "sync-approval.json"
    lock_path = state / "sync.lock"
    if lock_path.is_symlink():
        raise Refused("Lock symlink refused")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.action == "recover-status":
                return run_sync(checkout, "recover")
            sha = args.commit.lower()
            if not SHA.fullmatch(sha):
                raise Refused("Full 40-character commit required")
            if args.action == "plan":
                return run_sync(checkout, "plan", sha)
            if args.action == "authorise":
                if approval.exists() or approval.is_symlink():
                    raise Refused("Existing approval must be investigated and cleared locally")
                run_sync(checkout, "plan", sha)
                payload = {"repo": REPO, "checkout": str(checkout), "sha": sha,
                           "expires": time.time() + EXPIRY_SECONDS, "nonce": secrets.token_hex(16)}
                fd2 = os.open(approval, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd2, "w") as out:
                    json.dump(payload, out)
                    out.flush()
                    os.fsync(out.fileno())
                return "LOCAL APPROVAL CREATED: one use, expires in 10 minutes"
            private_file(approval)
            data = json.loads(approval.read_text())
            if data.get("repo") != REPO or data.get("checkout") != str(checkout) or data.get("sha") != sha or not (time.time() < data.get("expires", 0) <= time.time() + EXPIRY_SECONDS):
                raise Refused("Approval does not match checkout, SHA or expiry")
            # Consume before operation. A failed operation requires fresh local approval.
            approval.unlink()
            return run_sync(checkout, "apply", sha)
    finally:
        pass

if __name__ == "__main__":
    try:
        print(main())
    except (Refused, OSError, ValueError, KeyError, subprocess.TimeoutExpired, BlockingIOError) as exc:
        print("REFUSED: " + type(exc).__name__ + ": " + (str(exc) if isinstance(exc, Refused) else "local inspection required"), file=sys.stderr)
        raise SystemExit(2)
