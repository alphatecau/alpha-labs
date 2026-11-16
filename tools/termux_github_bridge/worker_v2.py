"""Termux bridge v0.2: bounded, manually triggered GitHub result relay.

No arbitrary commands, shell, background listener, or unreviewed result publication.
"""
import json
import pathlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

REPOSITORY = "alphatecau/alpha-labs"
LABEL = "termux-bridge-approved"
TOOLS = {"repo_status", "repo_log"}
REPOS = {"Q3HASH", "alpha-labs"}
STATE = pathlib.Path.home() / ".local/state/termux-github-bridge/tasks.sqlite3"

def run(argv, *, data=None, timeout=45):
    p = subprocess.run(argv, input=data, text=True, capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError("command returned failure")
    return p.stdout

def validate(issue):
    if issue.get("author", {}).get("login", "").lower() != "alphatecau":
        raise ValueError("unexpected author")
    if LABEL not in {label.get("name") for label in issue.get("labels", [])}:
        raise ValueError("approval label missing")
    body = json.loads(issue.get("body") or "")
    if type(body) is not dict or set(body) != {"schema", "tool", "repo"}:
        raise ValueError("invalid request fields")
    if type(body["schema"]) is not int or body["schema"] != 1:
        raise ValueError("unsupported schema")
    if body["tool"] not in TOOLS or body["repo"] not in REPOS:
        raise ValueError("operation not permitted")
    return body

def connect():
    STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(STATE)
    db.execute("CREATE TABLE IF NOT EXISTS executions (issue INTEGER PRIMARY KEY, status TEXT NOT NULL, started TEXT NOT NULL)")
    db.commit()
    STATE.chmod(0o600)
    return db

def reserve(db, issue):
    with db:
        cur = db.execute("INSERT OR IGNORE INTO executions VALUES (?, ?, ?)",
            (issue, "started", datetime.now(timezone.utc).isoformat()))
        return cur.rowcount == 1

def mark(db, issue, status):
    with db:
        db.execute("UPDATE executions SET status=? WHERE issue=?", (status, issue))

def execute(request):
    bridge = pathlib.Path.home() / "termux-mcp-bridge/bridge.py"
    if not bridge.is_file():
        raise RuntimeError("MCP bridge unavailable")
    msg = {"jsonrpc":"2.0","id":1,"method":"tools/call",
           "params":{"name":request["tool"],"arguments":{"repo":request["repo"]}}}
    raw = run([sys.executable, str(bridge)], data=json.dumps(msg)+"\n")
    response = json.loads(raw.splitlines()[0])
    if "error" in response or response.get("result", {}).get("isError"):
        raise RuntimeError("MCP tool error")
    # Deliberately discard stdout/stderr and git metadata: they may contain secrets.
    return "success"

def report(number, request, status):
    # Fixed metadata only, never raw command output or secret-bearing content.
    body = ("Termux bridge v0.2 execution receipt\n\n"
            f"- Task: #{number}\n- Tool: `{request['tool']}`\n"
            f"- Repository: `{request['repo']}`\n"
            f"- Status: **{status}**\n"
            "- Output: withheld locally for security\n")
    run(["gh","issue","comment",str(number),"-R",REPOSITORY,"--body",body])
    run(["gh","issue","close",str(number),"-R",REPOSITORY,"--reason","completed"])

def main():
    if "--execute" not in sys.argv:
        print("Dry run. Use --execute to process approved tasks.")
    issues = json.loads(run(["gh","issue","list","-R",REPOSITORY,"--state","open",
        "--label",LABEL,"--limit","30","--json","number,author,labels,body"]))
    db = connect()
    for issue in issues:
        number = issue["number"]
        try:
            request = validate(issue)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            print(f"#{number}: rejected")
            continue
        print(f"#{number}: approved {request['tool']} {request['repo']}")
        if "--execute" not in sys.argv:
            continue
        if not reserve(db, number):
            print(f"#{number}: replay blocked")
            continue
        try:
            status = execute(request)
        except (RuntimeError, OSError, ValueError, IndexError, json.JSONDecodeError, subprocess.TimeoutExpired):
            status = "failed"
        mark(db, number, status)
        try:
            report(number, request, status)
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            print(f"#{number}: result saved locally; GitHub receipt not confirmed")
        else:
            print(f"#{number}: {status}; GitHub receipt posted and issue closed")

if __name__ == "__main__":
    main()
