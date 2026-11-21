#!/usr/bin/env python3
"""Read-only reconciliation of local Level 3 staging files against audit entries.

This reports mismatches; it never edits, restores, or deletes files.
The audit journal is same-UID mutable and is not an independent trust anchor.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

try:
    from .github_pinned_install import ALLOWED, MAX_BYTES
    from .github_staging_audit import read_entries
except ImportError:
    from github_pinned_install import ALLOWED, MAX_BYTES
    from github_staging_audit import read_entries


def reconcile(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("invalid staging root")
    latest = {}
    entries = read_entries(root)
    for number, entry in enumerate(entries, 1):
        if entry.get("outcome") != "completed" or entry.get("operation") not in ("created", "updated"):
            continue
        path = entry.get("path")
        digest = entry.get("new_sha256")
        if not isinstance(path, str) or not ALLOWED.fullmatch(path):
            raise ValueError(f"invalid audited path on line {number}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"invalid audited hash on line {number}")
        latest[path] = digest
    results = []
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for path, digest in sorted(latest.items()):
            fds = []
            try:
                parent = root_fd
                parts = path.split("/")
                for part in parts[:-1]:
                    parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    fds.append(parent)
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                try:
                    import stat
                    st = os.fstat(fd)
                    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > MAX_BYTES:
                        status = "unsafe_file"
                    else:
                        with os.fdopen(fd, "rb", closefd=False) as stream:
                            actual = hashlib.sha256(stream.read(MAX_BYTES + 1)).hexdigest()
                        status = "match" if actual == digest else "mismatch"
                finally:
                    os.close(fd)
            except FileNotFoundError:
                status = "missing"
            except OSError:
                status = "unsafe_file"
            finally:
                for fd in reversed(fds):
                    os.close(fd)
            results.append({"path": path, "status": status, "expected_sha256": digest})
    finally:
        os.close(root_fd)
    return {"entries": len(entries), "files": results, "ok": all(item["status"] == "match" for item in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path.home() / "termux-level3-staging"))
    args = parser.parse_args()
    try:
        result = reconcile(args.root)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"RECONCILIATION FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
