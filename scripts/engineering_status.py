#!/usr/bin/env python3
"""Read-only GitHub engineering status report. No credentials or writes required."""
import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com/repos/alphatecau/alpha-labs"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "alpha-labs-engineering-audit/1.0"}

def fetch_json(path):
    request = urllib.request.Request(API + path, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)

def summarise(prs, runs):
    recent = runs.get("workflow_runs", [])
    by_sha = {}
    for run in recent:
        sha = run.get("head_sha")
        if sha:
            by_sha.setdefault(sha, []).append(run)
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only; no deployment, trading, merges or code changes",
        "open_prs": [
            {
                "number": p["number"],
                "title": p["title"],
                "draft": p["draft"],
                "url": p["html_url"],
                "head_sha": p["head"]["sha"],
                "recent_checks": [
                    {"name": r["name"], "status": r["status"], "conclusion": r.get("conclusion"), "url": r["html_url"]}
                    for r in by_sha.get(p["head"]["sha"], [])
                ],
            }
            for p in prs
        ],
        "note": "Only the returned first page of PRs and recent runs is inspected; absence of a check is not proof of passing.",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="engineering-status.json")
    args = parser.parse_args()
    try:
        prs = fetch_json("/pulls?state=open&per_page=100")
        runs = fetch_json("/actions/runs?per_page=100")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print("Read-only GitHub audit failed: " + str(exc), file=sys.stderr)
        return 1
    result = summarise(prs, runs)
    with open(args.output, "w", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(f"Wrote {args.output}; inspected {len(result['open_prs'])} open PRs")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
