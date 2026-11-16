"""Manual, fail-closed GitHub issue queue for Termux. No background execution."""
import json
import pathlib
import subprocess
import sys

REPO = "alphatecau/alpha-labs"
LABEL = "termux-bridge-approved"
TOOLS = {"repo_status", "repo_log"}
REPOS = {"Q3HASH", "alpha-labs"}

def validate(issue):
    if issue.get("author", {}).get("login", "").lower() != "alphatecau":
        raise ValueError("untrusted author")
    if LABEL not in {x.get("name") for x in issue.get("labels", [])}:
        raise ValueError("approval label missing")
    data = json.loads(issue.get("body") or "")
    if set(data) != {"schema", "tool", "repo"} or data["schema"] != 1:
        raise ValueError("invalid request")
    if data["tool"] not in TOOLS or data["repo"] not in REPOS:
        raise ValueError("operation not allowed")
    return data

def command(args, stdin=None):
    p = subprocess.run(args, input=stdin, text=True, capture_output=True, timeout=45)
    if p.returncode:
        raise RuntimeError("command failed (details withheld)")
    return p.stdout

def main():
    bridge = pathlib.Path.home() / "termux-mcp-bridge" / "bridge.py"
    if not bridge.is_file():
        raise RuntimeError("Termux MCP bridge missing")
    issues = json.loads(command(["gh", "issue", "list", "-R", REPO,
        "--state", "open", "--label", LABEL, "--limit", "20",
        "--json", "number,author,labels,body"]))
    for issue in issues:
        try:
            data = validate(issue)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            print(f"#{issue['number']}: rejected")
            continue
        print(f"#{issue['number']}: {data['tool']} {data['repo']} approved")
        if "--execute" not in sys.argv:
            continue
        request = {"jsonrpc":"2.0","id":1,"method":"tools/call",
            "params":{"name":data["tool"],"arguments":{"repo":data["repo"]}}}
        reply = json.loads(command([sys.executable, str(bridge)],
            json.dumps(request)+"\n").splitlines()[0])
        if "error" in reply or reply.get("result", {}).get("isError"):
            print("Bridge operation failed; issue unchanged")
            continue
        # Git metadata may contain sensitive information. Never publish it automatically.
        print("Result received locally. Review before manually posting:")
        print(json.dumps(reply["result"], ensure_ascii=True)[:2500])
        print("Issue intentionally left open; no automatic GitHub write.")

if __name__ == "__main__":
    main()
