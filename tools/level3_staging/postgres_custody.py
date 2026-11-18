"""Isolated PostgreSQL custody operations. Offline library, never exposed via HTTP.

Requires psycopg 3 and a dedicated, least-privilege Level 3 database role.
The caller owns the database connection; no credentials are logged or stored.
"""
import hashlib
import json
import re

class CustodyDenied(ValueError):
    pass

_NONCE=re.compile(r"^[a-f0-9]{64}$")
_PATH=re.compile(r"^(docs/level3-staging/[A-Za-z0-9_-]+\.md|tests/level3-staging/[A-Za-z0-9_-]+\.txt)$")

def _check(nonce,path,digest):
    if not isinstance(nonce,str) or not _NONCE.fullmatch(nonce):
        raise CustodyDenied("invalid nonce")
    if not isinstance(path,str) or not _PATH.fullmatch(path):
        raise CustodyDenied("invalid path")
    if not isinstance(digest,str) or not _NONCE.fullmatch(digest):
        raise CustodyDenied("invalid digest")

def claim(conn,remote_nonce,approval_nonce,path,digest):
    """Atomically reserve both nonces and record pending approval.

    Failure must roll back the entire transaction. Never retry a claimed nonce.
    """
    _check(approval_nonce,path,digest)
    if not isinstance(remote_nonce,str) or not _NONCE.fullmatch(remote_nonce):
        raise CustodyDenied("invalid remote nonce")
    with conn.transaction():
        conn.execute("INSERT INTO level3_custody.remote_nonce(nonce) VALUES (%s)",(remote_nonce,))
        conn.execute(
            "INSERT INTO level3_custody.approval_claim(nonce,path,payload_sha256,state) VALUES (%s,%s,%s,'claimed')",
            (approval_nonce,path,digest))
    return {"nonce":approval_nonce,"state":"claimed"}

def complete(conn,approval_nonce,path,digest):
    """Complete only an existing, matching claimed approval."""
    _check(approval_nonce,path,digest)
    with conn.transaction():
        result=conn.execute(
            "UPDATE level3_custody.approval_claim SET state='complete',completed_at=now() "
            "WHERE nonce=%s AND path=%s AND payload_sha256=%s AND state='claimed' RETURNING nonce",
            (approval_nonce,path,digest))
        if result.fetchone() is None:
            raise CustodyDenied("approval not claimed or already complete")
    return {"nonce":approval_nonce,"state":"complete"}

def pending(conn):
    """Read-only recovery inventory; never auto-complete interrupted writes."""
    rows=conn.execute(
        "SELECT nonce,path,payload_sha256 FROM level3_custody.approval_claim "
        "WHERE state='claimed' ORDER BY created_at,nonce").fetchall()
    return [{"nonce":r[0],"path":r[1],"sha256":r[2]} for r in rows]

def receipt_digest(receipt):
    """Deterministic receipt fingerprint for independent audit anchoring."""
    if not isinstance(receipt,dict):
        raise CustodyDenied("invalid receipt")
    raw=json.dumps(receipt,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()

def append_audit(conn,event_id,nonce,phase,digest):
    """Serialize chain append in a transaction. Requires an independent anchor to be tamper-evident."""
    import uuid
    if not isinstance(event_id,str):
        raise CustodyDenied("invalid event id")
    try:
        event_id=str(uuid.UUID(event_id))
    except ValueError as exc:
        raise CustodyDenied("invalid event id") from exc
    if not isinstance(nonce,str) or not _NONCE.fullmatch(nonce):
        raise CustodyDenied("invalid nonce")
    if not isinstance(digest,str) or not _NONCE.fullmatch(digest):
        raise CustodyDenied("invalid digest")
    if phase not in ("claimed","complete","recovered"):
        raise CustodyDenied("invalid phase")
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(4833443001)")
        row=conn.execute(
            "SELECT event_hash FROM level3_custody.audit_event ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous=row[0].strip() if row else "0"*64
        record={"event_id":event_id,"nonce":nonce,"phase":phase,
                "payload_sha256":digest,"previous_hash":previous}
        event_hash=receipt_digest(record)
        conn.execute(
            "INSERT INTO level3_custody.audit_event "
            "(event_id,nonce,phase,payload_sha256,previous_hash,event_hash) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (event_id,nonce,phase,digest,previous,event_hash))
    return {"event_hash":event_hash,"previous_hash":previous}
