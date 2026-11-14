"""Refuse all PostgreSQL integration targets except local disposable CI service."""
import os
from psycopg.conninfo import conninfo_to_dict


def require_disposable_ci_database(dsn):
    if os.environ.get("ALPHA_DISPOSABLE_PG_CI") != "1":
        raise RuntimeError("disposable CI approval marker required")
    if not isinstance(dsn, str) or not dsn:
        raise RuntimeError("disposable database DSN required")
    try:
        parts = conninfo_to_dict(dsn)
    except Exception as exc:
        raise RuntimeError("invalid disposable database DSN") from exc
    if parts.get("dbname") != "alpha_rls_test":
        raise RuntimeError("refusing non-disposable database name")
    if parts.get("host") not in ("127.0.0.1", "localhost"):
        raise RuntimeError("refusing non-loopback PostgreSQL host")
    if str(parts.get("port", "")) != "5432":
        raise RuntimeError("unexpected disposable PostgreSQL port")
    if parts.get("user") != "postgres":
        raise RuntimeError("disposable CI superuser required")
    if any(parts.get(k) for k in ("hostaddr", "service", "servicefile", "passfile")):
        raise RuntimeError("indirect PostgreSQL target forbidden")
    return dsn
