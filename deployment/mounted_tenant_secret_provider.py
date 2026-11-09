"""Read-only secret-provider adapter for a privately mounted credential bundle.

Mount the JSON bundle through an approved secrets system, outside the repo.
Never accept paths from requests. Reload on each lookup to support atomic
provider-side rotation; fail closed on missing or unsafe files.
"""
import json
import os
import re
import stat


class MountedTenantSecretProvider:
    def __init__(self, path):
        if not isinstance(path, str) or not os.path.isabs(path):
            raise ValueError("absolute trusted secret mount required")
        self.path = path

    def __call__(self, owner):
        if not isinstance(owner, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner):
            raise PermissionError("invalid verified account")
        fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077:
                raise PermissionError("secret file must be private and regular")
            if meta.st_size > 1048576:
                raise PermissionError("secret bundle too large")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(1048577)
            if len(data) > 1048576:
                raise PermissionError("secret bundle too large")
            bundle = json.loads(data)
            if not isinstance(bundle, dict) or bundle.get("schema_version") != 1 or not isinstance(bundle.get("accounts"), dict):
                raise PermissionError("invalid secret bundle")
            entry = bundle["accounts"].get(owner)
            if not isinstance(entry, dict):
                raise PermissionError("account not provisioned")
            return dict(entry)
        finally:
            os.close(fd)
