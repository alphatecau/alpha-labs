#!/usr/bin/env python3
"""Explicit, fail-closed GitHub -> Termux fast-forward synchronisation.

No daemon, no automatic deployment, no credentials, no trading operations.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPOSITORY = "alphatecau/alpha-labs"
REMOTE = "origin"
REMOTE_BRANCH = "main"
SHA = re.compile(r"^[0-9a-fA-F]{40}$")


class SyncError(Exception):
    pass


def git(*args, check=True):
    proc = subprocess.run(["git", *args], text=True, capture_output=True)
    if check and proc.returncode:
        raise SyncError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip(), proc.returncode


def require_clean():
    status, _ = git("status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise SyncError("Working tree is not clean (including untracked files). No changes made.")


def require_repository():
    root, _ = git("rev-parse", "--show-toplevel")
    if Path(root).resolve() != Path.cwd().resolve():
        raise SyncError("Run from the root of the intended Git checkout.")
    bare, _ = git("rev-parse", "--is-bare-repository")
    if bare != "false":
        raise SyncError("Bare repositories are unsupported.")
    url, _ = git("remote", "get-url", REMOTE)
    normalized = url.removesuffix(".git").rstrip("/")
    if normalized not in (
        f"https://github.com/{REPOSITORY}",
        f"git@github.com:{REPOSITORY}",
        f"ssh://git@github.com/{REPOSITORY}",
    ):
        raise SyncError("Origin is not the approved Alpha Labs repository.")
    gitdir, _ = git("rev-parse", "--absolute-git-dir")
    return Path(gitdir) / "termux-approved-sync.json"


def ancestor(older, newer):
    _, code = git("merge-base", "--is-ancestor", older, newer, check=False)
    return code == 0


def commit(ref):
    value, _ = git("rev-parse", "--verify", f"{ref}^{{commit}}")
    return value


def write_state(path, data):
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def write_state_replace(path, data):
    """Atomically replace an existing state record without exposing credentials."""
    tmp = path.with_name(path.name + ".new")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, indent=2)
            out.write("\\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    plan = sub.add_parser("plan", help="Fetch and validate an explicit 40-character commit SHA")
    plan.add_argument("--commit", required=True)
    apply = sub.add_parser("apply", help="Apply a previously planned SHA with explicit approval")
    apply.add_argument("--commit", required=True)
    apply.add_argument("--approve", action="store_true")
    recover = sub.add_parser("recover", help="Inspect or resolve an interrupted approved sync")
    recover.add_argument("--approve", action="store_true")
    rollback = sub.add_parser("rollback", help="Undo only the last recorded clean sync")
    rollback.add_argument("--approve", action="store_true")
    args = parser.parse_args()

    state_path = require_repository()
    require_clean()
    head = commit("HEAD")

    if args.action in ("plan", "apply"):
        if not SHA.fullmatch(args.commit):
            raise SyncError("Specify a full 40-character commit SHA, not a branch or tag.")
        target = args.commit.lower()
        if args.action == "plan":
            git("fetch", "--no-tags", REMOTE, REMOTE_BRANCH)
        target = commit(target)
        upstream = commit(f"refs/remotes/{REMOTE}/{REMOTE_BRANCH}")
        if not ancestor(target, upstream):
            raise SyncError("Selected SHA is not reachable from origin/main.")
        if not ancestor(head, target):
            raise SyncError("Not a fast-forward from current HEAD; refusing rewrite.")
        if args.action == "plan":
            print(f"CURRENT: {head}\nSELECTED: {target}\nREMOTE MAIN: {upstream}")
            print("FAST-FORWARD: YES\nWORKTREE: CLEAN")
            print("Review the selected commit before applying.")
            return
        if not args.approve:
            raise SyncError("Explicit --approve required.")
        if state_path.exists():
            raise SyncError("Previous sync record exists; rollback or archive it first.")
        if head == target:
            raise SyncError("Already at selected commit.")
        # Fetch again to detect a changed remote branch; never apply a stale plan.
        git("fetch", "--no-tags", REMOTE, REMOTE_BRANCH)
        upstream = commit(f"refs/remotes/{REMOTE}/{REMOTE_BRANCH}")
        if not ancestor(target, upstream):
            raise SyncError("Selected SHA no longer reachable from origin/main.")
        require_clean()
        if commit("HEAD") != head:
            raise SyncError("HEAD changed during verification.")
        backup = "termux-sync-backup/" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        git("branch", backup, head)
        write_state(state_path, {"before": head, "after": target, "backup": backup, "phase": "pending"})
        git("merge", "--ff-only", target)
        write_state_replace(state_path, {"before": head, "after": target, "backup": backup, "phase": "applied"})
        print(f"SYNC PASS: {head} -> {target}\nBACKUP: {backup}")
        print("Local runtime and test verification are still required.")
        return

    if args.action == "recover":
        if not state_path.is_file():
            raise SyncError("No sync record exists. Inspect backup branches and reflog manually.")
        data = json.loads(state_path.read_text())
        if data.get("phase") != "pending":
            raise SyncError("No interrupted sync pending.")
        if head == data["before"]:
            print("RECOVERY: merge not applied; previous HEAD intact.")
            if args.approve:
                state_path.unlink()
                print("RECOVERY PASS: pending record cleared; backup branch retained.")
            return
        if head == data["after"]:
            print("RECOVERY: merge completed; state finalisation pending.")
            if args.approve:
                data["phase"] = "applied"
                write_state_replace(state_path, data)
                print("RECOVERY PASS: sync state finalised; rollback available.")
            return
        raise SyncError("HEAD does not match recorded before/after SHA; manual review required.")

    if not args.approve:
        raise SyncError("Explicit --approve required.")
    if not state_path.is_file():
        raise SyncError("No recorded sync to roll back.")
    data = json.loads(state_path.read_text())
    if data.get("phase", "applied") != "applied":
        raise SyncError("Interrupted sync pending; run recover first.")
    if head != data["after"]:
        raise SyncError("HEAD differs from last synced SHA; rollback refused.")
    if not ancestor(data["before"], head):
        raise SyncError("Recorded rollback ancestor is invalid.")
    require_clean()
    # --keep refuses to overwrite local modifications, unlike --hard.
    git("reset", "--keep", data["before"])
    state_path.unlink()
    print(f"ROLLBACK PASS: {head} -> {data['before']}")
    print(f"Backup branch retained: {data['backup']}")


if __name__ == "__main__":
    try:
        main()
    except (SyncError, OSError, ValueError, KeyError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        sys.exit(2)
