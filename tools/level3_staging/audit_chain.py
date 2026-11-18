"""Durable append-only local audit journal with hash-chain verification.

A hash chain detects accidental corruption and unsynchronised edits; it is NOT
tamper-proof against an attacker who can rewrite the entire journal. Independent
off-device anchoring and distinct OS identity remain deployment requirements.
"""
import hashlib
import json
import os
import stat
from pathlib import Path

def canonical(record):
    return json.dumps(record,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()

def verify(path):
    prev="0"*64
    p=Path(path)
    if not p.exists():
        return prev
    if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode):
        raise ValueError("unsafe audit journal")
    with p.open("rb") as stream:
        for line in stream:
            record=json.loads(line)
            if set(record)!={"previous","event","digest"} or record["previous"]!=prev:
                raise ValueError("audit chain mismatch")
            digest=hashlib.sha256(canonical({"previous":prev,"event":record["event"]})).hexdigest()
            if digest!=record["digest"]:
                raise ValueError("audit digest mismatch")
            prev=digest
    return prev

def append(path,event):
    p=Path(path)
    if p.is_symlink():
        raise ValueError("unsafe audit symlink")
    if p.exists() and p.stat().st_mode & 0o077:
        raise PermissionError("audit journal permissions")
    prev=verify(p)
    record={"previous":prev,"event":event}
    record["digest"]=hashlib.sha256(canonical(record)).hexdigest()
    flags=os.O_APPEND|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC
    fd=os.open(p,flags,0o600)
    try:
        with os.fdopen(fd,"ab",closefd=False) as out:
            out.write(canonical(record)+b"\n")
            out.flush()
            os.fsync(out.fileno())
    finally:
        os.close(fd)
    return record["digest"]
