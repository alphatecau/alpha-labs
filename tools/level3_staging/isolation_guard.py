"""Deployment boundary guard: same-UID local custody is never production isolation."""
import os
from pathlib import Path

class IsolationDenied(RuntimeError):
    pass

def verify_isolation(worker_uid, broker_uid, ledger_path, audit_path):
    if not isinstance(worker_uid,int) or not isinstance(broker_uid,int):
        raise IsolationDenied("UID evidence required")
    if worker_uid == broker_uid:
        raise IsolationDenied("broker and worker must use distinct OS identities")
    for path in (ledger_path,audit_path):
        p=Path(path)
        if p.is_symlink() or not p.is_file():
            raise IsolationDenied("protected custody file missing or unsafe")
        st=p.stat()
        if st.st_uid != broker_uid or st.st_mode & 0o077:
            raise IsolationDenied("custody ownership or permissions invalid")
    return True

def local_worker_check(broker_uid, ledger_path, audit_path):
    return verify_isolation(os.getuid(),broker_uid,ledger_path,audit_path)
