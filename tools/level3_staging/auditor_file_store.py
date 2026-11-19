"""Auditor-only durable checkpoint store for a separately permissioned POSIX host.

This is not WORM storage: a privileged filesystem administrator can rewrite it.
Use only on an auditor-controlled host; broker must have no filesystem access.
"""
import fcntl
import json
import os
import re
from pathlib import Path


class AuditorStoreDenied(ValueError):
    pass


class AuditorFileStore:
    def __init__(self, root):
        self.root = Path(root)
        if self.root.is_symlink() or not self.root.is_dir():
            raise AuditorStoreDenied("invalid auditor storage root")
        if self.root.stat().st_mode & 0o077:
            raise AuditorStoreDenied("auditor storage must be private")

    def _path(self, key):
        if not isinstance(key, str) or re.fullmatch(
            r"level3-checkpoints/alpha-labs-level3_[A-Za-z0-9_-]+/[0-9]{20}-[0-9a-f]{64}\.json", key
        ) is None:
            raise AuditorStoreDenied("invalid checkpoint path")
        parent = self.root / "level3-checkpoints" / key.split("/")[1]
        for directory in (parent.parent, parent):
            if directory.is_symlink():
                raise AuditorStoreDenied("symlink directory")
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.stat().st_mode & 0o077:
                raise AuditorStoreDenied("unsafe directory permissions")
        return parent / key.split("/")[2]

    def _latest_path(self, audience):
        if not isinstance(audience, str) or re.fullmatch(
            r"alpha-labs-level3:[A-Za-z0-9_-]+", audience
        ) is None:
            raise AuditorStoreDenied("invalid audience")
        return self.root / ("latest-" + audience.replace(":", "_") + ".json")

    def create_once(self, key, data):
        if not isinstance(data, bytes):
            raise AuditorStoreDenied("checkpoint must be bytes")
        path = self._path(key)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as out:
                out.write(data)
                out.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        self._sync_directory(path.parent)

    def read(self, key):
        path = self._path(key)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            with os.fdopen(fd, "rb", closefd=False) as stream:
                return stream.read()
        finally:
            os.close(fd)

    def read_latest(self, audience):
        path = self._latest_path(audience)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        try:
            with os.fdopen(fd, "rb", closefd=False) as stream:
                return json.loads(stream.read())
        finally:
            os.close(fd)

    def advance_latest(self, audience, expected, new):
        path = self._latest_path(audience)
        lock = path.with_suffix(".lock")
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            current = self.read_latest(audience)
            if (current is None) != (expected is None):
                return False
            if current is not None and current.get("receipt") != expected:
                return False
            tmp = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
            raw = json.dumps(new, sort_keys=True, separators=(",", ":")).encode()
            outfd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(outfd, "wb", closefd=False) as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(outfd)
            finally:
                os.close(outfd)
            os.replace(tmp, path)
            self._sync_directory(self.root)
            return True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    @staticmethod
    def _sync_directory(path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
