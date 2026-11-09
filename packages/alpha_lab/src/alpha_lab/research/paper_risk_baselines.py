"""Research-only persistent risk reference points.

Append-only hash-linked SQLite records with restart verification. This does not
provide an external tamper-evident anchor: deleting an entire suffix or replacing
the database cannot be detected without independently retained checkpoints.
"""
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from alpha_lab.research.paper_simulator import number

class RiskBaselineJournal:
    def __init__(self, path):
        if path == ":memory:":
            raise ValueError("HALT: persistent risk database required")
        self.db = sqlite3.connect(path, timeout=5)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS risk_baselines (seq INTEGER PRIMARY KEY, previous_hash TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL)")
        self.db.commit()
        self.verify()

    def verify(self):
        previous="0"*64
        expected_seq=1
        latest=None
        for seq,prior,payload,digest in self.db.execute("SELECT seq,previous_hash,payload,digest FROM risk_baselines ORDER BY seq"):
            if seq!=expected_seq or prior!=previous or sha256((previous+payload).encode()).hexdigest()!=digest:
                raise ValueError("HALT: risk baseline journal integrity failure")
            record=json.loads(payload)
            if set(record)!={"day","day_start_nav","peak_nav","nav"}:
                raise ValueError("HALT: invalid baseline event")
            day=datetime.fromisoformat(record["day"])
            if day.tzinfo!=timezone.utc or day.time()!=datetime.min.time():
                raise ValueError("HALT: invalid UTC day")
            nav=number(record["nav"])
            start=number(record["day_start_nav"])
            peak=number(record["peak_nav"])
            if min(nav,start,peak)<=0 or peak<nav or peak<start:
                raise ValueError("HALT: invalid baseline values")
            if latest:
                prior_day=datetime.fromisoformat(latest["day"])
                if day<prior_day or peak<number(latest["peak_nav"]):
                    raise ValueError("HALT: non-monotonic baseline")
                if day==prior_day and start!=number(latest["day_start_nav"]):
                    raise ValueError("HALT: day-start NAV changed")
                if day>prior_day and start!=number(latest["nav"]):
                    raise ValueError("HALT: inconsistent day rollover")
            latest=record
            previous=digest
            expected_seq+=1
        return previous,latest

    def record(self, *, now, nav, expected_head=None):
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset()!=timedelta(0):
            raise ValueError("HALT: UTC timestamp required")
        n=number(nav)
        if n<=0:
            raise ValueError("HALT: invalid NAV")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            head,latest=self.verify()
            if expected_head is not None and head!=expected_head:
                raise ValueError("HALT: concurrent risk baseline modification")
            day=now.date().isoformat()+"T00:00:00+00:00"
            if latest:
                previous_day=datetime.fromisoformat(latest["day"])
                current_day=datetime.fromisoformat(day)
                if current_day<previous_day:
                    raise ValueError("HALT: clock moved backwards")
                start=number(latest["day_start_nav"]) if current_day==previous_day else number(latest["nav"])
                peak=max(n,number(latest["peak_nav"]))
            else:
                start=n
                peak=n
            event={"day":day,"day_start_nav":str(start),"peak_nav":str(peak),"nav":str(n)}
            payload=json.dumps(event,sort_keys=True,separators=(",",":"))
            digest=sha256((head+payload).encode()).hexdigest()
            self.db.execute("INSERT INTO risk_baselines(previous_hash,payload,digest) VALUES(?,?,?)",(head,payload,digest))
            self.db.commit()
            return digest,event
        except Exception:
            self.db.rollback()
            raise

    def close(self):
        self.db.close()
