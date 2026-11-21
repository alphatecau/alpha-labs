"""Restricted Termux Level 3 local approval queue.

Same-UID development prototype, NOT an independent security boundary.
No arbitrary paths, shell, network, trading, or unapproved file writes.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from pathlib import Path

ALLOW = re.compile(r"^(docs/level3-staging/[A-Za-z0-9_-]+\.md|tests/level3-staging/[A-Za-z0-9_-]+\.txt)$")
MAX_BYTES = 32768


class Refused(Exception):
    pass


def _safe_dir(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise Refused("unsafe directory")
    return path.resolve(strict=True)


def _state_dir(root):
    state = root / ".level3-local-approvals"
    if state.is_symlink():
        raise Refused("unsafe state directory")
    state.mkdir(mode=0o700, exist_ok=True)
    if state.stat().st_mode & 0o077:
        raise Refused("state directory permissions")
    return state


def _record(state, request_id):
    if not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise Refused("invalid request ID")
    file = state / (request_id + ".json")
    if file.is_symlink() or not file.is_file() or file.stat().st_mode & 0o077:
        raise Refused("invalid request record")
    return file


def propose(root, path, content):
    root = _safe_dir(root)
    if not isinstance(path, str) or not ALLOW.fullmatch(path) or not isinstance(content, str):
        raise Refused("path or content denied")
    data = content.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise Refused("oversize content")
    request_id = secrets.token_hex(16)
    state = _state_dir(root)
    record = {"id": request_id, "path": path, "content": content,
              "sha256": hashlib.sha256(data).hexdigest(), "status": "pending"}
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
    fd = os.open(state / (request_id + ".json"), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(record, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    return {"request_id": request_id, "path": path, "sha256": record["sha256"],
            "status": "pending", "operator_action": "local approval required"}


def approve(root, request_id):
    root = _safe_dir(root)
    file = _record(_state_dir(root), request_id)
    record = json.loads(file.read_text(encoding="utf-8"))
    if record.get("status") != "pending" or record.get("id") != request_id:
        raise Refused("not pending")
    print("Requested path:", record["path"])
    print("SHA-256:", record["sha256"])
    print("Content:\n" + record["content"])
    if input("Type APPROVE to authorise this exact create-only request: ") != "APPROVE":
        raise Refused("operator did not approve")
    record["status"] = "approved"
    # Same-UID approval queue is deliberately not represented as independent custody.
    temp = file.with_suffix(".tmp")
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(record, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, file)
    return {"request_id": request_id, "status": "approved"}


def apply(root, request_id):
    root = _safe_dir(root)
    file = _record(_state_dir(root), request_id)
    record = json.loads(file.read_text(encoding="utf-8"))
    if record.get("status") != "approved" or record.get("id") != request_id:
        raise Refused("operator approval missing")
    path, content = record["path"], record["content"]
    if not ALLOW.fullmatch(path) or not isinstance(content, str):
        raise Refused("invalid approved request")
    data = content.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    if len(data) > MAX_BYTES or digest != record["sha256"]:
        raise Refused("approved digest mismatch")
    # Parent must exist and contain no symlinks.
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in path.split("/")[:-1]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        out = os.open(path.split("/")[-1], os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                      0o600, dir_fd=fd)
        with os.fdopen(out, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(fd)
    finally:
        os.close(fd)
    # Record is single-use; if crash occurs after create, O_EXCL denies replay.
    record["status"] = "complete"
    temp = file.with_suffix(".tmp")
    out = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(out, "w", encoding="utf-8") as stream:
        json.dump(record, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, file)
    return {"request_id": request_id, "path": path, "sha256": digest, "status": "complete"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("approve",))
    parser.add_argument("request_id")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(approve(args.root, args.request_id)))
    except (Refused, OSError, ValueError, KeyError) as exc:
        raise SystemExit("Denied: " + type(exc).__name__) from exc


if __name__ == "__main__":
    main()
