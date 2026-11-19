"""Interactive Android signed Neon checkpoint launcher; credentials never echoed."""
import getpass
import os
from urllib.parse import urlsplit


def main():
    dsn = getpass.getpass("Paste direct Neon auditor connection string (hidden): ").strip()
    u = urlsplit(dsn)
    if (u.scheme not in ("postgresql", "postgres")
        or u.username != "level3_auditor_login"
        or not u.hostname or not u.hostname.endswith(".neon.tech")
        or "-pooler." in u.hostname
        or u.path != "/level3custody"
        or not u.password or "sslmode=require" not in u.query):
        raise SystemExit("BLOCKED: expected direct TLS Neon auditor connection")
    os.environ["LEVEL3_AUDITOR_READONLY_DSN"] = dsn
    from tools.level3_staging.auditor_android_checkpoint import main as checkpoint
    try:
        checkpoint()
    finally:
        os.environ.pop("LEVEL3_AUDITOR_READONLY_DSN", None)


if __name__ == "__main__":
    main()
