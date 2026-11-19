"""Interactive Android entrypoint for one authorised synthetic staging custody test.

The broker DSN is entered without terminal echo and kept only in process memory.
"""
import getpass
import os
from urllib.parse import urlsplit


def main():
    raw = getpass.getpass("Paste direct staging broker connection string (hidden): ").strip()
    u = urlsplit(raw)
    if (
        u.scheme not in ("postgresql", "postgres")
        or u.username != "level3_broker_login"
        or not u.hostname
        or not u.hostname.endswith(".neon.tech")
        or "-pooler." in u.hostname
        or u.path != "/level3custody"
        or not u.password
        or "sslmode=require" not in u.query
    ):
        raise SystemExit("BLOCKED: expected direct Neon level3_broker_login/level3custody DSN with TLS")
    os.environ["LEVEL3_STAGING_BROKER_DSN"] = raw
    os.environ["LEVEL3_STAGING_CUSTODY_SMOKE"] = "I_AUTHORISE_SYNTHETIC_STAGING_EVENT"
    from tools.level3_staging.staging_custody_smoke import main as run
    try:
        run()
    finally:
        os.environ.pop("LEVEL3_STAGING_BROKER_DSN", None)
        os.environ.pop("LEVEL3_STAGING_CUSTODY_SMOKE", None)


if __name__ == "__main__":
    main()
