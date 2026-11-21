"""Best-effort local audit journal for manually approved Level 3 staging operations.

This log is not tamper-proof against other processes with the same Android UID.
Entries are fsynced, but are not independently tamper-evident.
"""
import json
import os
from pathlib import Path
import time


def record(root, operation, outcome, commit, path, old_sha=None, new_sha=None):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("invalid staging root")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            os.mkdir(".level3-audit", mode=0o700, dir_fd=fd)
        except FileExistsError:
            pass
        audit = os.open(".level3-audit", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            journal = os.open("operations.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600, dir_fd=audit)
            try:
                entry = {"timestamp_utc": int(time.time()), "operation": operation,
                         "outcome": outcome, "commit": commit, "path": path,
                         "old_sha256": old_sha, "new_sha256": new_sha}
                data = (json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n").encode()
                os.write(journal, data)
                os.fsync(journal)
                os.fsync(audit)
            finally:
                os.close(journal)
        finally:
            os.close(audit)
    finally:
        os.close(fd)


def read_entries(root):
    path = Path(root) / ".level3-audit" / "operations.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]
