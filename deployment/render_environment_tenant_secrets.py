"""Render environment-group adapter for tenant credential configuration.

Supply ALPHA_TENANT_CREDENTIALS_JSON as a Render secret environment variable.
Never store this value in git or return it through HTTP. Rotation requires
updating the Render secret and restarting/redeploying the service; this adapter
does not claim hot rotation. Prefer a separate credential broker at scale.
"""
import json
import os
import re


class RenderEnvironmentTenantSecrets:
    def __init__(self, environ=None):
        self._environ = os.environ if environ is None else environ

    def __call__(self, owner):
        if not isinstance(owner, str) or not re.fullmatch(r"oidc_[0-9a-f]{64}", owner):
            raise PermissionError("invalid verified owner")
        raw = self._environ.get("ALPHA_TENANT_CREDENTIALS_JSON")
        if not isinstance(raw, str) or not 1 <= len(raw) <= 1048576:
            raise PermissionError("Render tenant secrets unavailable")
        try:
            data = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise PermissionError("invalid Render tenant secrets") from exc
        if (not isinstance(data, dict) or set(data) != {"schema_version", "accounts"}
                or data["schema_version"] != 1 or not isinstance(data["accounts"], dict)):
            raise PermissionError("invalid Render tenant secrets")
        credentials = data["accounts"].get(owner)
        if not isinstance(credentials, dict):
            raise PermissionError("unprovisioned owner")
        if (set(credentials) != {"host", "port", "dbname", "user", "password"}
                or not all(isinstance(credentials.get(k), str) and credentials[k]
                           for k in ("host", "dbname", "user", "password"))
                or type(credentials["port"]) is not int or not 1 <= credentials["port"] <= 65535
                or not re.fullmatch(r"alpha_tenant_[a-z0-9_]{1,80}", credentials["user"])):
            raise PermissionError("invalid tenant credential")
        return dict(credentials)
