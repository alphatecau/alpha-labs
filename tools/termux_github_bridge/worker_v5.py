"""Opt-in Ed25519 verified worker; never replaces running v0.3."""
import argparse
import json
import pathlib
import sqlite3
import subprocess
import time

import ed25519_protocol_v5 as protocol
import keyring_v5
import signed_protocol_v4 as v4
import worker_v2

LABEL = "termux-bridge-v5-signed"
STATE = pathlib.Path.home() / ".local/state/termux-github-bridge"
KEYRING = STATE / "v5-keys.json"
DB = STATE / "v5-receipts.sqlite3"

def connect(path=DB):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise v4.Rejected("insecure state directory")
    if path.is_symlink():
        raise v4.Rejected("database symlink denied")
    db = sqlite3.connect(path)
    path.chmod(0o600)
    db.execute("CREATE TABLE IF NOT EXISTS tasks (issue INTEGER PRIMARY KEY, nonce TEXT UNIQUE NOT NULL, operation TEXT NOT NULL, repo TEXT NOT NULL, status TEXT NOT NULL)")
    db.commit()
    return db

def validate(issue, keys, device, now=None):
    if issue.get("author", {}).get("login", "").lower() != "alphatecau":
        raise v4.Rejected("unauthorised author")
    if LABEL not in {label.get("name") for label in issue.get("labels", [])}:
        raise v4.Rejected("approval label absent")
    envelope = json.loads(issue.get("body") or "")
    return protocol.verify(envelope, keys, device, now=now)

def reserve(db, number, task):
    try:
        with db:
            db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (number, task["nonce"], task["operation"], task["repo"], "reserved"))
    except sqlite3.IntegrityError as exc:
        raise v4.Rejected("issue or nonce replay") from exc

def receipt(db, number, status):
    with db:
        db.execute("UPDATE tasks SET status=? WHERE issue=?", (status, number))

def publish(number, operation, repo, status):
    body = ("Termux v0.5 signed-task receipt\n\n"
            f"- Task: #{number}\n- Operation: `{operation}`\n"
            f"- Repository: `{repo}`\n- Status: **{status}**\n"
            "- Output: withheld locally\n")
    worker_v2.run(["gh","issue","comment",str(number),"-R",worker_v2.REPOSITORY,"--body",body])
    worker_v2.run(["gh","issue","close",str(number),"-R",worker_v2.REPOSITORY,"--reason","completed"])

def reconcile(db, open_issues):
    # Re-publish recorded terminal receipts without repeating execution.
    open_ids = {issue["number"] for issue in open_issues}
    for number, operation, repo, status in db.execute(
        "SELECT issue, operation, repo, status FROM tasks WHERE status IN ('success','failed')"):
        if number in open_ids:
            publish(number, operation, repo, status)

def process(issue, keys, device, db, execute=False, now=None):
    task = validate(issue, keys, device, now)
    if not execute:
        return "verified-only"
    number = issue["number"]
    reserve(db, number, task)
    try:
        status = worker_v2.execute({"tool":task["operation"],"repo":task["repo"]})
    except (RuntimeError, OSError, ValueError, IndexError, json.JSONDecodeError, subprocess.TimeoutExpired):
        status = "failed"
    receipt(db, number, status)
    publish(number, task["operation"], task["repo"], status)
    return status

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not v4.DEVICE.fullmatch(args.device):
        parser.error("invalid device")
    keys = keyring_v5.trusted_keys(KEYRING)
    if not keys:
        raise SystemExit("No trusted signing keys; refusing to poll")
    db = connect()
    issues = json.loads(worker_v2.run(["gh","issue","list","-R",worker_v2.REPOSITORY,
        "--state","open","--label",LABEL,"--limit","100",
        "--json","number,author,labels,body"]))
    if args.execute:
        reconcile(db, issues)
    for issue in issues:
        try:
            print(f"#{issue['number']}: {process(issue,keys,args.device,db,args.execute)}")
        except (v4.Rejected, ValueError, TypeError, KeyError, json.JSONDecodeError):
            print(f"#{issue.get('number','?')}: rejected")
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            print(f"#{issue.get('number','?')}: execution/receipt unavailable; inspect local ledger")

if __name__ == "__main__":
    main()
