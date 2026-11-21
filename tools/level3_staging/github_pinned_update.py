#!/usr/bin/env python3
"""Manual, pinned GitHub staging update with optimistic concurrency and local audit.

No MCP exposure. Operator must separately review the immutable commit and both
file hashes. Existing files are updated only if their SHA-256 matches --old-sha256.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

try:
    from .github_pinned_install import ALLOWED, SHA, DIGEST, MAX_BYTES, fetch
except ImportError:
    from github_pinned_install import ALLOWED, SHA, DIGEST, MAX_BYTES, fetch

def update(root, commit, relative, old_sha, new_sha, fetcher=fetch):
    if not SHA.fullmatch(commit) or not DIGEST.fullmatch(old_sha) or not DIGEST.fullmatch(new_sha):
        raise ValueError("full lowercase commit SHA and both SHA-256 digests required")
    if not ALLOWED.fullmatch(relative):
        raise ValueError("path outside staging allowlist")
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("invalid staging root")
    data = fetcher(commit, relative)
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != new_sha:
        raise ValueError("new content hash mismatch or oversized file")
    fds = [os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
    tmpname = None
    try:
        parent = fds[0]
        parts = relative.split("/")
        for part in parts[:-1]:
            parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            fds.append(parent)
        name = parts[-1]
        existing = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            st = os.fstat(existing)
            if not __import__("stat").S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > MAX_BYTES:
                raise ValueError("target is not a safe regular staging file")
            with os.fdopen(existing, "rb", closefd=False) as stream:
                current = stream.read(MAX_BYTES + 1)
            if hashlib.sha256(current).hexdigest() != old_sha:
                raise ValueError("existing file changed: update refused")
        finally:
            os.close(existing)
        # Create temporary file in the same verified parent directory.
        for attempt in range(10):
            candidate = ".level3-update-" + os.urandom(12).hex()
            try:
                fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                tmpname = candidate
                break
            except FileExistsError:
                continue
        else:
            raise OSError("cannot allocate temporary file")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # Recheck the target before replace. Same-UID adversarial races are
            # not prevented; this is NOT a hostile-process security boundary.
            checkfd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                with os.fdopen(checkfd, "rb") as stream:
                    if hashlib.sha256(stream.read(MAX_BYTES + 1)).hexdigest() != old_sha:
                        raise ValueError("target changed during update")
            finally:
                pass
            os.replace(tmpname, name, src_dir_fd=parent, dst_dir_fd=parent)
            tmpname = None
            os.fsync(parent)
        finally:
            if tmpname is not None:
                os.unlink(tmpname, dir_fd=parent)
        return {"status": "updated", "commit": commit, "path": relative,
                "old_sha256": old_sha, "new_sha256": new_sha}
    finally:
        for fd in reversed(fds):
            os.close(fd)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(Path.home() / "termux-level3-staging"))
    p.add_argument("--commit", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--old-sha256", required=True)
    p.add_argument("--new-sha256", required=True)
    a = p.parse_args()
    try:
        print(json.dumps({"commit": a.commit, "path": a.path,
                          "old_sha256": a.old_sha256, "new_sha256": a.new_sha256}, indent=2))
        if input("Type UPDATE to replace this staging file: ").strip() != "UPDATE":
            raise ValueError("operator declined")
        print(json.dumps(update(a.root, a.commit, a.path, a.old_sha256, a.new_sha256)))
    except (ValueError, OSError) as exc:
        print(f"DENIED: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
