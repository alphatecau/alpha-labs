#!/usr/bin/env python3
"""Read-only Level 3 staging recovery report.

Use this to identify changes needing manual recovery. Never deletes, restores,
or edits files; do not treat same-UID journal records as trusted authorisation.
"""
import argparse
import json
from pathlib import Path
import sys

try:
    from .github_staging_reconcile import reconcile
except ImportError:
    from github_staging_reconcile import reconcile


def recovery_report(root):
    status = reconcile(root)
    affected = [item for item in status["files"] if item["status"] != "match"]
    return {
        "status": "attention_required" if affected else "consistent",
        "audit_entries": status["entries"],
        "affected_files": affected,
        "next_action": (
            "Inspect affected files manually and compare with independently reviewed GitHub commits; "
            "do not overwrite until verified."
            if affected else "No recorded file mismatch detected."
        ),
        "limitations": [
            "Unrecorded files are not checked.",
            "An interrupted write before journal append may not be recorded.",
            "Same-UID processes can alter this journal.",
            "No automatic restoration or rollback is performed.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(Path.home() / "termux-level3-staging"))
    args = p.parse_args()
    try:
        report = recovery_report(args.root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "consistent" else 1
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"RECOVERY REPORT FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
