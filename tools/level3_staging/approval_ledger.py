"""Experimental SQLite approval ledger; NOT an independent authority or live MCP write service."""
import hashlib
import hmac
import json
import os
import sqlite3
import time
from pathlib import Path

class ApprovalDenied(Exception):
    pass

def _canonical(operation, path, sha256, expires_at, nonce):
    return json.dumps({'operation':operation,'path':path,'sha256':sha256,'expires_at':expires_at,'nonce':nonce},sort_keys=True,separators=(',',':')).encode()

def sign(secret, operation, path, sha256, expires_at, nonce):
    return hmac.new(secret, _canonical(operation,path,sha256,expires_at,nonce), hashlib.sha256).hexdigest()

def _connect(db):
    db=Path(db)
    if db.is_symlink():
        raise ApprovalDenied('symlink database')
    if db.exists() and (not db.is_file() or db.stat().st_mode & 0o077):
        raise ApprovalDenied('database permissions')
    previous_umask=os.umask(0o077)
    try:
        con=sqlite3.connect(str(db),timeout=2,isolation_level=None)
    finally:
        os.umask(previous_umask)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=FULL')
    con.execute("CREATE TABLE IF NOT EXISTS approvals (nonce TEXT PRIMARY KEY, operation TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, expires_at INTEGER NOT NULL, signature TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('approved','claimed','completed')))")
    return con

def issue(db, secret, path, sha256, expires_at, nonce):
    if not isinstance(nonce,str) or len(nonce)<32 or not isinstance(expires_at,int):
        raise ApprovalDenied('invalid nonce or expiry')
    sig=sign(secret,'create',path,sha256,expires_at,nonce)
    con=_connect(db)
    try:
        con.execute('BEGIN IMMEDIATE')
        con.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?,?)',(nonce,'create',path,sha256,expires_at,sig,'approved'))
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK')
        raise
    finally:
        con.close()

def claim(db, secret, path, sha256, nonce, now=None):
    clock=int(time.time() if now is None else now)
    con=_connect(db)
    try:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT operation,path,sha256,expires_at,signature,state FROM approvals WHERE nonce=?',(nonce,)).fetchone()
        if not row:
            raise ApprovalDenied('unknown approval')
        operation,approved_path,approved_hash,expiry,signature,state=row
        expected=sign(secret,operation,approved_path,approved_hash,expiry,nonce)
        if not (state=='approved' and operation=='create' and path==approved_path and sha256==approved_hash and clock<expiry<=clock+600 and hmac.compare_digest(signature,expected)):
            raise ApprovalDenied('approval invalid, expired, or consumed')
        if con.execute("UPDATE approvals SET state='claimed' WHERE nonce=? AND state='approved'",(nonce,)).rowcount!=1:
            raise ApprovalDenied('concurrent claim')
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK')
        raise
    finally:
        con.close()

def complete(db, nonce):
    con=_connect(db)
    try:
        con.execute('BEGIN IMMEDIATE')
        if con.execute("UPDATE approvals SET state='completed' WHERE nonce=? AND state='claimed'",(nonce,)).rowcount!=1:
            raise ApprovalDenied('not claimed')
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK')
        raise
    finally:
        con.close()
