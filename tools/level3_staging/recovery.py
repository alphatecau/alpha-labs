"""Read-only crash reconciliation report for consumed Level 3 approvals.

Never auto-reissue, delete, complete or retry claimed approvals. Operator must
investigate ambiguous claims; fail closed.
"""
import sqlite3
from pathlib import Path
from tools.level3_staging.signed_create import _database

def inspect_claims(db_path):
    if not Path(db_path).exists():
        return {"status":"missing-ledger","claims":[],"blocked":True}
    con=_database(db_path)
    try:
        rows=con.execute("SELECT nonce,state FROM claims ORDER BY nonce").fetchall()
    finally:
        con.close()
    return {"status":"review-required" if any(state!="complete" for _,state in rows) else "consistent",
            "claims":[{"nonce":nonce,"state":state} for nonce,state in rows],
            "blocked":any(state!="complete" for _,state in rows)}
