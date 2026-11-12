#!/usr/bin/env python3
"""Reconcile immutable Git/GitHub snapshots without changing branches or index.

Git merge-tree may create unreachable objects; it never merges into a ref.
Original branch-creation tips are not exposed by GitHub and are not fabricated.
"""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], text=True,
                          capture_output=True, timeout=90)


def ancestor(repo, older, newer):
    result = git(repo, "merge-base", "--is-ancestor", older, newer)
    if result.returncode not in (0, 1):
        raise ValueError("Git ancestry could not be verified")
    return result.returncode == 0


def tree(repo, ref):
    result = git(repo, "ls-tree", "-r", ref)
    result.check_returncode()
    entries = {}
    for line in result.stdout.splitlines():
        info, path = line.split("\t", 1)
        entries[path] = info.split()[2]
    return entries


def reserved(path):
    return "2027" in path and ("dataset" in path.lower() or "holdout" in path.lower())


def latest_runs(runs):
    latest = {}
    for run in sorted(runs, key=lambda r: (r["created_at"], r["id"]), reverse=True):
        latest.setdefault((run["workflow_id"], run["event"]), run)
    return list(latest.values())


def classify(*, incorporated, historical, failed, missing_ci, conflicts, reviewed):
    if incorporated:
        return "ALREADY_INTEGRATED"
    if historical:
        return "HISTORICAL_RETAIN"
    if missing_ci:
        return "BLOCKED"
    if failed:
        return "REPAIR_REQUIRED"
    if conflicts:
        return "INTEGRATION_REQUIRED"
    return "READY_FOR_REVIEW" if reviewed else "INTEGRATION_REQUIRED"


def reconcile(repo, metadata, ci):
    main = metadata["main_sha"]
    branches = metadata["branches"]
    heads = {b["name"]: b["commit"]["sha"] for b in branches}
    ci_by_name = {b["name"]: b for b in ci["branches"]}
    main_tree = tree(repo, main)
    records = []
    priority = {92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 103, 104, 105}
    for index, branch in enumerate(branches, 1):
        name, head = branch["name"], branch["commit"]["sha"]
        prs = [p for p in metadata["prs"] if p["head"]["ref"] == name]
        base_ref = prs[0]["base"]["ref"] if prs else "main"
        base_tip = heads.get(base_ref)
        fork = git(repo, "merge-base", main, head)
        fork.check_returncode()
        fork_sha = fork.stdout.strip()
        delta = git(repo, "diff", "--name-status", fork_sha, head)
        delta.check_returncode()
        changed = [line.split("\t")[-1] for line in delta.stdout.splitlines()]
        head_tree = tree(repo, head)
        incorporated_by_history = ancestor(repo, head, main)
        incorporated_by_content = bool(changed) and all(
            head_tree.get(p) == main_tree.get(p) for p in changed)
        merged_main_prs = [p for p in prs if p["merged_at"] and p["base"]["ref"] == "main"
                           and p["head"]["sha"] == head and p["merge_commit_sha"]
                           and ancestor(repo, p["merge_commit_sha"], main)]
        incorporated = incorporated_by_history or incorporated_by_content or bool(merged_main_prs)
        blocked_data = [p for p in changed if reserved(p)]
        if incorporated:
            conflict_state, conflicts = "NOT_APPLICABLE", []
        elif blocked_data:
            conflict_state, conflicts = "BLOCKED", []
        else:
            merge = git(repo, "merge-tree", "--write-tree", "--name-only", "--no-messages", main, head)
            conflict_state = "VERIFIED" if merge.returncode in (0, 1) else "BLOCKED"
            conflicts = [p for p in merge.stdout.splitlines()[1:] if p] if merge.returncode == 1 else []
        evidence = ci_by_name.get(name, {"state": "BLOCKED", "runs": []})
        exact_runs = [r for r in evidence.get("runs", []) if r.get("head_sha") == head]
        evidence_complete = (evidence["state"] == "VERIFIED" and evidence.get("head_sha") == head
                             and len(exact_runs) == len(evidence.get("runs", [])))
        checks = latest_runs(exact_runs)
        failed = [r for r in checks if r["conclusion"] in ("failure", "timed_out", "startup_failure")]
        reviewed = any(p["number"] in priority for p in prs)
        historical = not reviewed and (not prs or any(
            word in name for word in ("strategy-v0.", "multi-asset-v0.", "behaviour-simulation")))
        disposition = classify(incorporated=incorporated, historical=historical,
                               failed=bool(failed), missing_ci=not checks or not evidence_complete,
                               conflicts=bool(conflicts), reviewed=reviewed)
        if blocked_data or conflict_state == "BLOCKED":
            disposition = "BLOCKED"
        equivalence = {"status": "NOT_INSPECTED", "basis": "No semantic equivalence claim"}
        if any(p["number"] == 99 and p["head"]["sha"] == head == "09f9c9870d9b2bb9ed77b6cba6aaff6591b0300e" for p in prs):
            disposition = "SUPERSEDED"
            equivalence = {"status": "VERIFIED", "basis": "Four original PR #99 unittest methods executed successfully against main's quote implementation; equivalent assertions are already in merged #98. Not byte-identical."}
        if any(p["number"] == 92 and p["head"]["sha"] == head == "6f5250b82a8242f58bfbe564c527dd233d965b8e" for p in prs):
            disposition = "SUPERSEDED"
            equivalence = {"status": "VERIFIED", "basis": "Successor #94 includes #92 ancestry and repairs reproduced HTTP truncation, malformed-result and stale-head defects; integrate the stronger successor rather than #92 alone."}
        risks = []
        domains = {
            "identity": ("auth", "oidc", "session", "proxy"),
            "database": ("postgres", "rls", "tenant", "journal"),
            "execution_and_risk": ("paper", "risk", "execution", "ledger"),
            "ci_permissions": (".github/",),
            "market_data": ("quote", "market_feed", "data/"),
        }
        for domain, terms in domains.items():
            if any(any(term in p.lower() for term in terms) for p in changed):
                risks.append(domain)
        signature = hashlib.sha256(json.dumps(
            [(p, head_tree.get(p)) for p in sorted(changed)], separators=(",", ":")).encode()).hexdigest()
        ahead_behind = git(repo, "rev-list", "--left-right", "--count", main + "..." + head)
        behind, ahead = map(int, ahead_behind.stdout.split())
        records.append({
            "name": name, "head_sha": head, "status": "VERIFIED",
            "associated_prs": [{"number": p["number"], "state": p["state"],
                                "merged_at": p["merged_at"], "url": p["url"]} for p in prs],
            "base": {"declared_ref": base_ref, "current_base_sha": base_tip,
                     "observed_pr_base_shas": [p["base"]["sha"] for p in prs],
                     "main_merge_base_sha": fork_sha,
                     "inferred_declared_base_fork_sha": git(repo, "merge-base", base_tip, head).stdout.strip() if base_tip else None,
                     "original_creation_sha": None, "original_creation_status": "NOT_INSPECTED",
                     "reason": "GitHub has no original creation-tip field; merge base is inferred Git ancestry, not original creation provenance."},
            "main_comparison": {"ahead": ahead, "behind": behind,
                                "ancestor_of_main": incorporated_by_history,
                                "all_delta_files_equal_main": incorporated_by_content,
                                "verified_main_merge_prs": [p["number"] for p in merged_main_prs]},
            "semantic_equivalence": equivalence,
            "changed_files": changed,
            "unique_delta_files": [p for p in changed if head_tree.get(p) != main_tree.get(p)],
            "delta_signature": signature,
            "dependencies": {"base_missing": base_tip is None,
                             "base_ahead_of_branch": base_tip is not None and not ancestor(repo, base_tip, head),
                             "changed_manifests": [p for p in changed if p.endswith(("pyproject.toml", "package.json", "requirements.txt", "ruff.toml"))]},
            "merge_conflicts": {"status": conflict_state, "against_main": conflicts},
            "ci": {"status": "VERIFIED" if evidence_complete else "BLOCKED", "total_runs": evidence.get("total", 0),
                   "latest_per_workflow_event": checks, "failed_run_ids": [r["id"] for r in failed]},
            "risk_domains": risks,
            "source_review_status": "VERIFIED" if reviewed else "NOT_INSPECTED",
            "source_review_level": "priority targeted review" if reviewed else "automated ancestry, file-delta, dependency and conflict inspection; not line-by-line security approval",
            "reserved_data_skipped": blocked_data,
            "disposition": disposition,
        })
        if index % 10 == 0:
            print(f"Reconciled {index}/{len(branches)} branches", flush=True)
    groups = {}
    for r in records:
        if r["changed_files"]:
            groups.setdefault(r["delta_signature"], []).append(r["name"])
    for r in records:
        r["identical_delta_branches"] = [name for name in groups.get(r["delta_signature"], []) if name != r["name"]]
    return {"generated_utc": datetime.now(timezone.utc).isoformat(),
            "snapshot_observed_at": metadata["observed_at"], "main_sha": main,
            "status": "VERIFIED", "branch_count": len(records),
            "open_pr_count": sum(p["state"] == "open" for p in metadata["prs"]),
            "disposition_counts": dict(Counter(r["disposition"] for r in records)),
            "limits": ["Inventory and CI are timestamped snapshots; later branch updates require recollection at their new exact SHAs.",
                       "Original branch creation tips require unavailable reflogs/audit provenance and are not fabricated.",
                       "Ancestry/content equivalence is not independent security approval.",
                       "Historical branches are retained; no branches/PRs are deleted, closed or merged.",
                       "Reserved prospective data is never read; protected paths block content merging."],
            "branches": records}


def markdown(report):
    lines = ["# Branch reconciliation", "", f"Snapshot main: `{report['main_sha']}`.",
             f"Inventoried **{report['branch_count']} remote branches** and **{report['open_pr_count']} open PRs**.",
             "", "Machine evidence: `branch-reconciliation.json`. Every row is an observed snapshot, not merge approval.",
             "Original creation SHAs are NOT_INSPECTED because GitHub does not expose them; declared bases and computed merge bases are recorded.",
             "Historical line-by-line security review remains NOT_INSPECTED unless explicitly recorded.", "",
             "| Branch | Head | PRs | Disposition | CI failures | Main conflicts |",
             "|---|---|---|---|---|---|"]
    for r in report["branches"]:
        prs = ", ".join(f"#{p['number']}" for p in r["associated_prs"]) or "—"
        lines.append(f"| `{r['name']}` | `{r['head_sha'][:10]}` | {prs} | {r['disposition']} | {len(r['ci']['failed_run_ids'])} | {len(r['merge_conflicts']['against_main'])} |")
    lines += ["", "## Limits", "", *["- " + x for x in report["limits"]], ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--ci", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("docs/audits"))
    args = parser.parse_args()
    report = reconcile(args.repository, json.loads(args.metadata.read_text()), json.loads(args.ci.read_text()))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "branch-reconciliation.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "branch-reconciliation.md").write_text(markdown(report))
    print(json.dumps({"branches": report["branch_count"], "dispositions": report["disposition_counts"]}))


if __name__ == "__main__":
    main()
