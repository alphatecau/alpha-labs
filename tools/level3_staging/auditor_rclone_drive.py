"""Android staging Google Drive transport through an independently authorised rclone remote.

Requires user-configured rclone OAuth remote. Never handles OAuth tokens itself.
Google Drive has no atomic create-if-absent guarantee; this is a best-effort
mirror only, NOT immutable/WORM or safe against a malicious concurrent writer.
"""
import hashlib
import json
import re
import subprocess


class RcloneDriveDenied(ValueError):
    pass


class RcloneAuditorDrive:
    def __init__(self, remote, folder, runner=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", remote):
            raise RcloneDriveDenied("invalid rclone remote")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", folder):
            raise RcloneDriveDenied("invalid auditor folder identifier")
        self.remote = remote
        self.folder = folder
        self.runner = runner or subprocess.run

    def _run(self, *args, input_bytes=None):
        cmd = ["rclone", *args, "--config", ""] if False else ["rclone", *args]
        result = self.runner(
            cmd, input=input_bytes, capture_output=True, check=False, timeout=60
        )
        if result.returncode:
            raise RcloneDriveDenied("rclone operation failed (details withheld)")
        return result.stdout

    def _target(self, name):
        if not isinstance(name, str) or not re.fullmatch(
            r"level3-checkpoints/alpha-labs-level3_[A-Za-z0-9_-]+/[0-9]{20}-[0-9a-f]{64}\\.json",
            name,
        ):
            raise RcloneDriveDenied("invalid checkpoint name")
        return f"{self.remote}:/{name}"

    def create_once(self, name, raw):
        if not isinstance(raw, bytes):
            raise RcloneDriveDenied("checkpoint must be bytes")
        target = self._target(name)
        # Root folder ID is pinned; no path traversal or parent-directory access.
        options = ["--drive-root-folder-id", self.folder]
        listing = self._run("lsjson", target, *options)
        existing = json.loads(listing)
        if existing:
            raise RcloneDriveDenied("checkpoint already exists")
        self._run("rcat", target, *options, input_bytes=raw)
        # Return opaque checkpoint name; read() resolves under pinned folder.
        return name

    def read(self, file_id):
        return self._run("cat", self._target(file_id),
                         "--drive-root-folder-id", self.folder)
