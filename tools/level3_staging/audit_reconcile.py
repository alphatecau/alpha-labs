"""Fail-closed reconciliation of transactional audit outbox and journal.

Read-only: never replays writes, resets nonces, or invents missing audit entries.
"""
import json
from pathlib import Path
from tools.level3_staging.audit_chain import verify
from tools.level3_staging.signed_create import _database

def inspect_outbox(db_path, audit_path):
    if not Path(db_path).is_file() or not Path(audit_path).is_file():
        return {"blocked": True, "reason": "missing evidence"}
    verify(audit_path)
    con = _database(db_path)
    try:
        rows = con.execute(
            "SELECT nonce,phase,path,sha256 FROM audit_outbox ORDER BY nonce,phase"
        ).fetchall()
    finally:
        con.close()
    expected = {
        (nonce,phase,path,digest)
        for nonce,phase,path,digest in rows
    }
    observed = set()
    with Path(audit_path).open("r",encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)["event"]
            if not isinstance(event,dict) or set(event) != {"phase","nonce","path","sha256"}:
                return {"blocked": True, "reason": "unexpected journal event"}
            item=(event["nonce"],event["phase"],event["path"],event["sha256"])
            if item in observed:
                return {"blocked": True, "reason": "duplicate journal event"}
            observed.add(item)
    if not observed.issubset(expected):
        return {"blocked": True, "reason": "journal contains unknown entries"}
    missing=expected-observed
    return {"blocked":bool(missing),"reason":"undelivered audit intent" if missing else "consistent",
            "pending_count":len(missing),"outbox_count":len(expected)}
