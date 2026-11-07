"""Tenant-scoped, single-host durable transactions and hash-chained audit events.

SQLite is a development adapter, not a multi-host production database. The trusted
service process owns SQL access; agents and HTTP clients never receive it.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3

from .contracts import (Forbidden, Mode, Principal, canonical, digest, identifier,
                        number, timestamp, utc)


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Do not chmod an existing caller-owned parent directory.
        if not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        os.chmod(self.path, 0o600)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS accounts(
                    tenant TEXT NOT NULL, id TEXT NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(tenant,id));
                CREATE TABLE IF NOT EXISTS positions(
                    tenant TEXT NOT NULL, account TEXT NOT NULL,
                    instrument TEXT NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(tenant,account,instrument));
                CREATE TABLE IF NOT EXISTS orders(
                    tenant TEXT NOT NULL, account TEXT NOT NULL, key TEXT NOT NULL,
                    request_hash TEXT NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(tenant,account,key));
                CREATE TABLE IF NOT EXISTS quotes(
                    tenant TEXT NOT NULL, account TEXT NOT NULL,
                    instrument TEXT NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(tenant,account,instrument));
                CREATE TABLE IF NOT EXISTS events(
                    tenant TEXT NOT NULL, seq INTEGER NOT NULL,
                    account TEXT NOT NULL, body TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, hash TEXT NOT NULL,
                    PRIMARY KEY(tenant,seq));
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def account(db, principal: Principal, account_id: str, *, write=False):
        identifier(account_id)
        if write and principal.role != "operator":
            raise Forbidden("operator permission required")
        row = db.execute("SELECT record FROM accounts WHERE tenant=? AND id=?",
                         (principal.tenant, account_id)).fetchone()
        if row is None:
            raise Forbidden("account unavailable")
        return json.loads(row[0])

    def create_account(self, principal: Principal, account_id: str, *,
                       initial_cash="10000", currency="AUD", mode=Mode.SIMULATION,
                       now: str | None = None, limits=None):
        from .risk import Limits
        if principal.role != "operator":
            raise Forbidden("operator permission required")
        identifier(account_id)
        if currency not in {"AUD", "USD", "USDT", "USDC", "EUR", "GBP"}:
            raise ValueError("unsupported reporting currency")
        mode = Mode(mode)
        if mode != Mode.SIMULATION:
            raise ValueError("only local simulation accounts can be provisioned")
        initial_cash = str(number(initial_cash, positive=True))
        now = now or timestamp()
        moment = utc(now)
        limits = limits or Limits()
        if not isinstance(limits, Limits):
            raise ValueError("validated Limits required")
        account = dict(id=account_id, currency=currency, mode=mode, cash=initial_cash,
                       initial_cash=initial_cash, last_equity=initial_cash,
                       peak_equity=initial_cash, day_start=initial_cash,
                       week_start=initial_cash, day=moment.date().isoformat(),
                       week=moment.strftime("%G-W%V"), last_time=now,
                       realised_pnl="0", fees="0", halted=False, halt_reason="",
                       enabled=False, limits=json.loads(canonical(limits)))
        with self.transaction() as db:
            db.execute("INSERT INTO accounts VALUES(?,?,?)",
                       (principal.tenant, account_id, canonical(account)))
            self.event(db, principal, account_id, "ACCOUNT_CREATED", account, now)

    @staticmethod
    def save_account(db, principal, account):
        db.execute("UPDATE accounts SET record=? WHERE tenant=? AND id=?",
                   (canonical(account), principal.tenant, account["id"]))

    @staticmethod
    def rows(db, table, principal, account_id):
        if table not in {"positions", "orders", "quotes"}:
            raise ValueError("invalid store collection")
        return [json.loads(r[0]) for r in db.execute(
            f"SELECT record FROM {table} WHERE tenant=? AND account=? ORDER BY rowid",
            (principal.tenant, account_id))]

    @staticmethod
    def event(db, principal, account_id, kind, payload, now):
        utc(now)
        last = db.execute("SELECT seq, hash FROM events WHERE tenant=? ORDER BY seq DESC LIMIT 1",
                          (principal.tenant,)).fetchone()
        seq, previous = (last[0]+1, last[1]) if last else (1, "0"*64)
        body = canonical(dict(schema="alpha-labs.audit.v1", seq=seq, account=account_id,
                              actor=principal.subject, kind=kind, timestamp=now, payload=payload))
        hashed = digest(dict(tenant=principal.tenant, previous_hash=previous, body=body))
        db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",
                   (principal.tenant, seq, account_id, body, previous, hashed))

    def events(self, principal, account_id):
        with self.transaction() as db:
            self.account(db, principal, account_id)
            return [json.loads(r[0]) for r in db.execute(
                "SELECT body FROM events WHERE tenant=? AND account=? ORDER BY seq",
                (principal.tenant, account_id))]

    @staticmethod
    def _verify_audit(db, principal):
        previous, expected = "0"*64, 1
        for row in db.execute("SELECT * FROM events WHERE tenant=? ORDER BY seq", (principal.tenant,)):
            if (row["seq"] != expected or row["previous_hash"] != previous
                    or row["hash"] != digest(dict(tenant=principal.tenant,
                                                  previous_hash=previous, body=row["body"]))):
                return False
            previous, expected = row["hash"], expected+1
        return True

    def verify_audit(self, principal):
        with self.transaction() as db:
            return self._verify_audit(db, principal)

    def _bundle(self, db, principal, account_id):
        account = self.account(db, principal, account_id)
        snapshot = dict(schema="alpha-labs.snapshot.v1", account=account,
                        positions=self.rows(db, "positions", principal, account_id),
                        orders=self.rows(db, "orders", principal, account_id),
                        live_trading_enabled=False, production_deployment_enabled=False)
        audit_ok = self._verify_audit(db, principal)
        events = [json.loads(r[0]) for r in db.execute(
            "SELECT body FROM events WHERE tenant=? AND account=? ORDER BY seq",
            (principal.tenant, account_id))] if audit_ok else []
        return snapshot, events, audit_ok

    def bundle(self, principal, account_id):
        """One consistent transaction for account, journal and reconciliation input."""
        with self.transaction() as db:
            return self._bundle(db, principal, account_id)

    def snapshot(self, principal, account_id):
        with self.transaction() as db:
            account = self.account(db, principal, account_id)
            return dict(schema="alpha-labs.snapshot.v1", account=account,
                        positions=self.rows(db, "positions", principal, account_id),
                        orders=self.rows(db, "orders", principal, account_id),
                        live_trading_enabled=False, production_deployment_enabled=False)

    def backup(self, destination: Path):
        destination = Path(destination)
        if destination.resolve() == self.path.resolve() or destination.exists():
            raise ValueError("backup destination must be new")
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        source = self.connect()
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
