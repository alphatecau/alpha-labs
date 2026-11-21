"""Durable, single-use nonce ledger for a future isolated Level 3 writer.

The ledger is only a replay control, NOT an independent approval boundary.
The caller must verify the signed approval first. This module never writes targets.
"""
import os
from pathlib import Path
import re
import sqlite3

NONCE = re.compile(r"^[0-9a-f]{32}$")


class ReplayDenied(ValueError):
    pass


def consume(db_path, nonce, digest):
    if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
        raise ReplayDenied("invalid nonce")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ReplayDenied("invalid digest")
    db_path = Path(db_path)
    if db_path.is_symlink() or (db_path.exists() and not db_path.is_file()):
        raise ReplayDenied("unsafe ledger")
    if db_path.parent.is_symlink() or not db_path.parent.is_dir():
        raise ReplayDenied("unsafe ledger directory")
    connection = sqlite3.connect(str(db_path), timeout=5, isolation_level=None)
    try:
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("CREATE TABLE IF NOT EXISTS consumed (nonce TEXT PRIMARY KEY, digest TEXT NOT NULL)")
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("INSERT INTO consumed(nonce,digest) VALUES (?,?)", (nonce, digest))
            connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            connection.execute("ROLLBACK")
            raise ReplayDenied("approval already consumed") from exc
        except BaseException:
            connection.execute("ROLLBACK")
            raise
    finally:
        connection.close()
    os.chmod(db_path, 0o600)
    return {"nonce": nonce, "status": "consumed"}
