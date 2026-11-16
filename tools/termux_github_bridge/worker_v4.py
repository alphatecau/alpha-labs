"""Opt-in signed GitHub task worker. Never replaces the v0.3 worker automatically."""
import argparse
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import time

import signed_protocol_v4 as protocol
import worker_v2

LABEL = "termux-bridge-v4-signed"
STATE_DIR = pathlib.Path.home() / ".local/state/termux-github-bridge"
KEY_FILE = STATE_DIR / "v4-signing.key"
NONCE_DB = STATE_DIR / "v4-nonces.sqlite3"

def read_key(path=KEY_FILE):
    st = path.stat()
    if st.st_mode & 0o077:
        raise RuntimeError("signing key permissions must be 0600")
    key = path.read_bytes()
    if len(key) != 32:
        raise RuntimeError("signing key must contain exactly 32 raw bytes")
    return key

def parse_issue(issue):
    if issue.get("author", {}).get("login", "").lower() != "alphatecau":
        raise protocol.Rejected("unexpected issue author")
    if LABEL not in {label.get("name") for label in issue.get("labels", [])}:
        raise protocol.Rejected("signed approval label missing")
    envelope = json.loads(issue.get("body") or "")
    return envelope

def connect_db(path=NONCE_DB):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    os.chmod(path, 0o600)
    return db

def execute_task(task):
    return worker_v2.execute({"tool": task["operation"], "repo": task["repo"]})

def report(number, task, status):
    # Only fixed allowlisted metadata is published; no command output or signatures.
    body = ("Termux bridge v0.4 signed-task receipt\n\n"
            f"- Task: #{number}\n- Operation: `{task['operation']}`\n"
            f"- Repository: `{task['repo']}`\n"
            f"- Status: **{status}**\n- Output: withheld locally\n")
    worker_v2.run(["gh", "issue", "comment", str(number), "-R",
                   worker_v2.REPOSITORY, "--body", body])
    worker_v2.run(["gh", "issue", "close", str(number), "-R",
                   worker_v2.REPOSITORY, "--reason", "completed"])

def process(issue, key, device, db, execute=False, now=None):
    envelope = parse_issue(issue)
    task = protocol.verify(envelope, key, device, now=now)
    if not execute:
        return "verified-only"
    protocol.reserve_nonce(db, task)
    try:
        status = execute_task(task)
    except (RuntimeError, OSError, ValueError, IndexError, json.JSONDecodeError,
            subprocess.TimeoutExpired):
        status = "failed"
    report(issue["number"], task, status)
    return status

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--device", required=True)
    args = parser.parse_args(argv)
    if not protocol.DEVICE.fullmatch(args.device):
        parser.error("invalid device identifier")
    key = read_key()
    issues = json.loads(worker_v2.run(["gh", "issue", "list", "-R",
        worker_v2.REPOSITORY, "--state", "open", "--label", LABEL,
        "--limit", "30", "--json", "number,author,labels,body"]))
    db = connect_db()
    for issue in issues:
        try:
            result = process(issue, key, args.device, db, args.execute)
            print(f"#{issue['number']}: {result}", flush=True)
        except (protocol.Rejected, ValueError, TypeError, KeyError, json.JSONDecodeError):
            print(f"#{issue.get('number', '?')}: rejected", flush=True)
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            print(f"#{issue.get('number', '?')}: execution or receipt error", flush=True)

if __name__ == "__main__":
    main()
