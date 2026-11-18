"""Durable remote request replay guard; store on persistent broker-owned storage."""
import os
import sqlite3
import stat
from pathlib import Path
from tools.level3_staging.remote_auth import RemoteDenied

def claim_once(path,nonce):
    p=Path(path)
    if p.is_symlink() or (p.exists() and
        (not stat.S_ISREG(p.stat().st_mode) or p.stat().st_mode & 0o077)):
        raise RemoteDenied("unsafe replay database")
    if p.parent.stat().st_mode & 0o077:
        raise RemoteDenied("replay database parent must be private")
    old=os.umask(0o077)
    try:
        db=sqlite3.connect(str(p),timeout=5,isolation_level=None)
    finally:
        os.umask(old)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS remote_nonces (nonce TEXT PRIMARY KEY)")
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO remote_nonces(nonce) VALUES (?)",(nonce,))
        db.execute("COMMIT")
        return True
    except sqlite3.IntegrityError as exc:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise RemoteDenied("replayed remote request") from exc
    finally:
        db.close()
