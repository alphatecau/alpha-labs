#!/usr/bin/env python3
"""Operator-run, GitHub-mediated Level 3 staging installer.

This is NOT an MCP tool. The operator supplies a reviewed, immutable commit SHA
and the expected SHA-256 of the file contents. No tokens or GitHub credentials.
Only create-only staging files are supported in this first phase.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

REPO = "alphatecau/alpha-labs"
ALLOWED = re.compile(r"(?:docs/level3-staging/[A-Za-z0-9_-]+\.md|tests/level3-staging/[A-Za-z0-9_-]+\.txt)\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_BYTES = 32768

def fetch(commit, path):
    url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{path}"
    with urlopen(Request(url, headers={"User-Agent": "alpha-labs-level3-staging/1"}), timeout=20) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("file exceeds 32 KiB")
    return data

def install(root, commit, relative, expected_sha, fetcher=fetch):
    if not SHA.fullmatch(commit) or not DIGEST.fullmatch(expected_sha):
        raise ValueError("full lowercase commit SHA and SHA-256 required")
    if not ALLOWED.fullmatch(relative):
        raise ValueError("path outside staging allowlist")
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("staging root must be an existing real directory")
    data = fetcher(commit, relative)
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("content digest mismatch or oversized content")
    parts = relative.split("/")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory_fds = [root_fd]
    try:
        parent_fd = root_fd
        for component in parts[:-1]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            directory_fds.append(next_fd)
            parent_fd = next_fd
        target = parts[-1]
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            with os.fdopen(fd, "wb", closefd=False) as output:
                output.write(data)
                output.flush()
                os.fsync(fd)
        except BaseException:
            os.unlink(target, dir_fd=parent_fd)
            raise
        finally:
            os.close(fd)
        os.fsync(parent_fd)
        return {"status": "created", "commit": commit, "path": relative, "sha256": expected_sha}
    finally:
        for fd in reversed(directory_fds):
            os.close(fd)

def audit_result(root, result):
    try:
        from .github_staging_audit import record
    except ImportError:
        from github_staging_audit import record
    record(root, result["status"], "completed", result["commit"], result["path"],
           result.get("old_sha256"), result.get("new_sha256", result.get("sha256")))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path.home() / "termux-level3-staging"))
    parser.add_argument("--commit", required=True, help="reviewed 40-character GitHub commit SHA")
    parser.add_argument("--path", required=True, help="allowlisted staging file path")
    parser.add_argument("--sha256", required=True, help="reviewed file SHA-256")
    args = parser.parse_args()
    try:
        print("REVIEWED COMMIT:", args.commit)
        print("TARGET:", args.path)
        print("EXPECTED SHA-256:", args.sha256)
        if input("Type INSTALL to create this staging file: ").strip() != "INSTALL":
            raise ValueError("operator declined")
        result = install(args.root, args.commit, args.path, args.sha256)
        audit_result(args.root, result)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError) as exc:
        print(f"DENIED: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
