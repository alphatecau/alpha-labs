#!/usr/bin/env python3
"""Read-only, exact-head GitHub Actions evidence; never a release approval."""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode

API = "https://api.github.com/repos/alphatecau/alpha-labs"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "alpha-labs-engineering-audit/1.0"}
PAGE_SIZE = 100
MAX_PR_PAGES = 100
MAX_RUN_PAGES = 10  # GitHub caps filtered workflow-run searches at 1,000 results.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
COLLECTION_BUDGET_SECONDS = 8 * 60


class CollectionError(Exception):
    """A safe diagnostic without response bodies, URLs or authentication data."""


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectionError("GitHub API redirect refused")


def fetch_json(path):
    if (not isinstance(path, str) or not path.startswith("/")
            or path.startswith("//") or "://" in path or "#" in path):
        raise CollectionError("invalid repository API path")
    headers = dict(HEADERS)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        request = urllib.request.Request(API + path, headers=headers, method="GET")
        opener = urllib.request.build_opener(RejectRedirects())
        with opener.open(request, timeout=15) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise CollectionError("GitHub API response too large")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise CollectionError(f"GitHub API HTTP {exc.code}") from None
    except (OSError, ValueError):
        raise CollectionError("GitHub API request or JSON decoding failed") from None


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value) is not None


def _valid_pr(pr):
    return (isinstance(pr, dict) and type(pr.get("number")) is int
            and pr["number"] > 0 and isinstance(pr.get("title"), str)
            and type(pr.get("draft")) is bool and isinstance(pr.get("html_url"), str)
            and isinstance(pr.get("head"), dict) and _sha(pr["head"].get("sha")))


def _valid_run(run, sha):
    return (isinstance(run, dict) and type(run.get("id")) is int and run["id"] > 0
            and run.get("head_sha") == sha and isinstance(run.get("name"), str)
            and isinstance(run.get("event"), str) and isinstance(run.get("status"), str)
            and (run.get("conclusion") is None or isinstance(run["conclusion"], str))
            and isinstance(run.get("html_url"), str))


def summarise(prs, runs, *, main_sha=None, coverage=None, errors=None, prs_complete=True):
    by_sha = {}
    for run in runs.get("workflow_runs", []):
        by_sha.setdefault(run["head_sha"], {})[run["id"]] = run

    def snapshot(sha):
        checks, other = [], []
        for run in sorted(by_sha.get(sha, {}).values(), key=lambda r: r["id"], reverse=True):
            item = {"id": run["id"], "event": run["event"], "name": run["name"],
                    "status": run["status"], "conclusion": run.get("conclusion"),
                    "url": run["html_url"]}
            if run["event"] in ("push", "pull_request"):
                checks.append(item)
            else:
                # workflow_dispatch can check out an input ref unrelated to head_sha.
                item["target_verified"] = False
                other.append(item)
        retrieved = sha is not None and (coverage is None or coverage.get(sha) == "complete")
        state = ("complete" if checks else "missing") if retrieved else "incomplete"
        return {"head_sha": sha, "collection_state": state,
                "recent_checks": checks, "other_runs": other}

    main = snapshot(main_sha)
    open_prs = [{"number": p["number"], "title": p["title"], "draft": p["draft"],
                 "url": p["html_url"], **snapshot(p["head"]["sha"])} for p in prs]
    complete = (prs_complete and main_sha is not None and not errors
                and all(p["collection_state"] != "incomplete" for p in [main, *open_prs]))
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only; no deployment, trading, merges or code changes",
        "main": main,
        "open_prs": open_prs,
        "collection": {"state": "complete" if complete else "incomplete",
                       "pull_requests_complete": prs_complete, "errors": errors or []},
        "note": "GitHub Actions evidence for observed head SHAs only; absence of a check is not proof of passing. "
                "Collection completeness is not CI success, required-check coverage, security approval or merge approval. "
                "Other events do not establish the tested checkout; refs may change after observation.",
    }


def collect(*, fetch=None, clock=time.monotonic, budget=COLLECTION_BUDGET_SECONDS):
    fetch = fetch or fetch_json
    started = clock()
    prs, runs, coverage, errors = [], [], {}, []
    main_sha, prs_complete = None, False
    stage = "main"

    def request(path):
        if clock() - started >= budget:
            raise CollectionError("collection time budget exhausted")
        result = fetch(path)
        if clock() - started >= budget:
            raise CollectionError("collection time budget exhausted")
        return result

    try:
        branch = request("/branches/main")
        if (not isinstance(branch, dict) or not isinstance(branch.get("commit"), dict)
                or not _sha(branch["commit"].get("sha"))):
            raise CollectionError("invalid main branch response")
        main_sha = branch["commit"]["sha"]

        stage = "open pull requests"
        seen_prs = set()
        for page in range(1, MAX_PR_PAGES + 1):
            batch = request("/pulls?" + urlencode({"state": "open", "per_page": PAGE_SIZE, "page": page}))
            if not isinstance(batch, list) or len(batch) > PAGE_SIZE:
                raise CollectionError("invalid pull request page")
            for pr in batch:
                if not _valid_pr(pr) or pr["number"] in seen_prs:
                    raise CollectionError("invalid or repeated pull request")
                seen_prs.add(pr["number"])
                prs.append(pr)
            if len(batch) < PAGE_SIZE:
                prs_complete = True
                break
        if not prs_complete:
            raise CollectionError("pull request pagination limit reached")

        for sha in dict.fromkeys([main_sha, *(p["head"]["sha"] for p in prs)]):
            stage = "workflow runs for " + sha
            coverage[sha] = "incomplete"
            seen_runs, expected = set(), 0
            for page in range(1, MAX_RUN_PAGES + 1):
                data = request("/actions/runs?" + urlencode({"head_sha": sha, "per_page": PAGE_SIZE, "page": page}))
                if (not isinstance(data, dict) or type(data.get("total_count")) is not int
                        or data["total_count"] < 0 or not isinstance(data.get("workflow_runs"), list)
                        or len(data["workflow_runs"]) > PAGE_SIZE):
                    raise CollectionError("invalid workflow run page")
                expected = max(expected, data["total_count"])
                for run in data["workflow_runs"]:
                    if not _valid_run(run, sha):
                        raise CollectionError("invalid or mismatched workflow run")
                    if run["id"] not in seen_runs:
                        seen_runs.add(run["id"])
                        runs.append(run)
                if len(seen_runs) >= expected:
                    coverage[sha] = "complete"
                    break
                if len(data["workflow_runs"]) < PAGE_SIZE:
                    raise CollectionError("workflow run results truncated or changed during collection")
            if coverage[sha] != "complete":
                raise CollectionError("workflow run pagination limit reached")
    except CollectionError as exc:
        errors.append({"stage": stage, "reason": str(exc)})
    except (OSError, ValueError, TypeError):
        # Injected transports and malformed JSON must not print raw responses/secrets.
        errors.append({"stage": stage, "reason": "GitHub evidence request failed"})
    return summarise(prs, {"workflow_runs": runs}, main_sha=main_sha,
                     coverage=coverage, errors=errors, prs_complete=prs_complete)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="engineering-status.json")
    args = parser.parse_args()
    result = collect()
    try:
        with open(args.output, "w", encoding="utf-8") as output:
            json.dump(result, output, indent=2)
            output.write("\n")
    except OSError:
        print("Could not write engineering status report", file=sys.stderr)
        return 1
    complete = result["collection"]["state"] == "complete"
    print(f"Wrote {args.output}; {result['collection']['state']} collection of {len(result['open_prs'])} observed open PRs")
    if not complete:
        print("GitHub evidence collection incomplete; inspect the report diagnostics", file=sys.stderr)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
