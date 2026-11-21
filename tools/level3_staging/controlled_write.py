"""Level 3 staging-only file creation prototype. NOT safe to expose as a network MCP server."""
import ctypes
import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path

ALLOW = re.compile(r"^(docs/level3-staging/[A-Za-z0-9_-]+\.md|tests/level3-staging/[A-Za-z0-9_-]+\.txt)$")
MAX_BYTES = 32768

class Refused(Exception):
    pass

def digest(content):
    if not isinstance(content, str):
        raise Refused("text required")
    data = content.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise Refused("payload too large")
    return hashlib.sha256(data).hexdigest()

def _directory(root, relative):
    if not isinstance(relative, str) or not ALLOW.fullmatch(relative):
        raise Refused("path not allowlisted")
    parts = relative.split("/")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(root, flags)
    try:
        for component in parts[:-1]:
            new_fd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = new_fd
        return fd, parts[-1]
    except BaseException:
        os.close(fd)
        raise

def propose(root, relative, content):
    checksum = digest(content)
    fd, name = _directory(root, relative)
    try:
        try:
            os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return {"operation": "create", "path": relative, "sha256": checksum, "bytes": len(content.encode("utf-8"))}
        raise Refused("destination exists")
    finally:
        os.close(fd)

def _consume_approval(approval_file, consumed):
    """Atomically claim approval without replacing an existing consumed record."""
    if hasattr(os, "link"):
        os.link(approval_file, consumed, follow_symlinks=False)
        try:
            approval_file.unlink()
        except BaseException as exc:
            raise Refused("approval consumption incomplete; manual inspection required") from exc
    else:
        # Android/Termux Python may omit os.link. Linux renameat2 with
        # RENAME_NOREPLACE is atomic and refuses an existing destination.
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = libc.renameat2
        except (AttributeError, OSError) as exc:
            raise Refused("atomic approval consumption unavailable") from exc
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        at_fdcwd = -100
        if renameat2(at_fdcwd, os.fsencode(approval_file),
                     at_fdcwd, os.fsencode(consumed), 1) != 0:
            error = ctypes.get_errno()
            raise Refused("atomic approval consumption refused") from OSError(error, os.strerror(error))
    try:
        dfd = os.open(approval_file.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except BaseException as exc:
        raise Refused("approval consumption incomplete; manual inspection required") from exc


def apply(root, relative, content, approval_file, audit_file, now=None):
    """Offline proof of concept. Approval ledger and audit are NOT production-hardened."""
    proposal = propose(root, relative, content)
    approval_file, audit_file = Path(approval_file), Path(audit_file)
    root = Path(root).resolve(strict=True)
    if approval_file.parent.resolve().is_relative_to(root) or audit_file.parent.resolve().is_relative_to(root):
        raise Refused("control paths must be outside workspace")
    if approval_file.is_symlink() or audit_file.is_symlink():
        raise Refused("symlink control file")
    # Open the validated approval without following symlinks. Keep the inode
    # open through consumption to detect a pathname swap before the claim.
    approval_fd = os.open(approval_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(approval_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise Refused("approval ownership or mode invalid")
        if info.st_size > 4096:
            raise Refused("approval file too large")
        with os.fdopen(os.dup(approval_fd), "rb") as stream:
            approval_bytes = stream.read(4097)
        if len(approval_bytes) > 4096:
            raise Refused("approval file too large")
        if audit_file.exists():
            audit_info = audit_file.stat()
            if not stat.S_ISREG(audit_info.st_mode) or audit_info.st_uid != os.getuid() or stat.S_IMODE(audit_info.st_mode) != 0o600:
                raise Refused("audit ownership or mode invalid")
        approval = json.loads(approval_bytes.decode("utf-8"))
        clock = time.time() if now is None else now
        if (not isinstance(approval, dict) or set(approval) != {"operation","path","sha256","expires_at"}
            or approval["operation"] != "create" or approval["path"] != relative
            or approval["sha256"] != proposal["sha256"]
            or type(approval["expires_at"]) not in (int,float)
            or not clock < approval["expires_at"] <= clock + 600):
            raise Refused("approval mismatch or expired")
        consumed = approval_file.with_name(approval_file.name + ".consumed")
        if consumed.exists():
            raise Refused("consumed record already exists")
        _consume_approval(approval_file, consumed)
        # The consumed pathname must still refer to the exact inode validated
        # above, with the same contents. Otherwise fail closed before writing.
        claimed_fd = os.open(consumed, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            claimed_info = os.fstat(claimed_fd)
            if (claimed_info.st_dev, claimed_info.st_ino) != (info.st_dev, info.st_ino):
                raise Refused("approval changed during consumption")
            with os.fdopen(os.dup(claimed_fd), "rb") as stream:
                if stream.read(4097) != approval_bytes:
                    raise Refused("approval contents changed during consumption")
        finally:
            os.close(claimed_fd)
    finally:
        os.close(approval_fd)
    fd, name = _directory(root, relative)
    try:
        out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
        with os.fdopen(out, "wb") as stream:
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(fd)
    finally:
        os.close(fd)
    record = {"operation":"create","path":relative,"sha256":proposal["sha256"],"timestamp":int(clock)}
    audit_fd = os.open(audit_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(audit_fd, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return record
