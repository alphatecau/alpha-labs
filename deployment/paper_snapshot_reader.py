"""Serve only operator-pinned, owner-bound, stopped paper journals."""
import base64
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import monotonic

from alpha_lab.research.coinbase_paper_book import PRODUCTS, SOURCE
from alpha_lab.research.local_paper_recovery import inspect_journal, snapshot_read_only
from alpha_lab.research.paper_journal import journal_tables
from alpha_lab.research.paper_market import COINBASE_MARKET
from deployment.paper_aud import aud_result, rba_series, utc

OWNER = re.compile(r"oidc_[a-f0-9]{64}")
DIGEST = re.compile(r"[a-f0-9]{64}")
PAGE_SIZE = 30
MAX_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Binding:
    account: str
    sha256: str
    sequence: int
    head: str
    captured_at: str


def configured_reader(env):
    value = env.get("ALPHA_PAPER_JOURNALS_JSON")
    if not value:
        return None
    return StoppedPaperSnapshotReader(json.loads(value), directory=env.get("ALPHA_PAPER_JOURNAL_DIR", "/etc/secrets"))


class StoppedPaperSnapshotReader:
    def __init__(self, journals, *, directory, fx_source=rba_series):
        self.directory = Path(directory)
        if not self.directory.is_absolute() or not isinstance(journals, dict) or not 1 <= len(journals) <= 16:
            raise ValueError("private snapshot directory and tenant mapping required")
        self.bindings = {}
        digests = set()
        for owner, raw in journals.items():
            binding = Binding(**raw)
            if (not OWNER.fullmatch(owner) or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", binding.account)
                    or not DIGEST.fullmatch(binding.sha256) or binding.sha256 in digests
                    or not DIGEST.fullmatch(binding.head) or type(binding.sequence) is not int
                    or binding.sequence < 0 or utc(binding.captured_at) > datetime.now(timezone.utc)):
                raise ValueError("invalid or shared paper snapshot binding")
            self.bindings[owner] = binding
            digests.add(binding.sha256)
        self.fx_source = fx_source
        self.cache = {}
        self.fx = None
        self.next_fx = 0
        self.lock = Lock()

    def snapshot(self, owner, *, page=0):
        binding = self.bindings.get(owner)
        if binding is None:
            raise PermissionError("tenant journal unprovisioned")
        with self.lock:
            if owner not in self.cache:
                self.cache[owner] = self._load(binding)
            report, fills, orders = self.cache[owner]
            if self.fx is None and monotonic() >= self.next_fx:
                self.next_fx = monotonic() + 300
                try:
                    self.fx = self.fx_source()
                except Exception:
                    pass  # Offline USD verification remains independently available.
            if "aud" not in report and self.fx is not None:
                try:
                    report["aud"] = aud_result(fills, report, utc(binding.captured_at), self.fx)
                except (ValueError, TypeError, ArithmeticError, KeyError, IndexError):
                    report["aud"] = None
            start, end = PAGE_SIZE * page, PAGE_SIZE * (page + 1)
            return {**report, "aud": report.get("aud"), "page": page,
                    "fills": list(reversed(fills[max(0, len(fills) - end):max(0, len(fills) - start)])), "orders": None if orders is None else orders[start:end],
                    "next_page": page + 1 if max(len(fills), len(orders or [])) > end else None}

    def _load(self, binding):
        # The filename is a verified digest. A request can never select a filesystem path.
        raw = self.directory / (binding.sha256 + ".sqlite3")
        with TemporaryDirectory(prefix="alpha-paper-readonly-") as temporary:
            copy = Path(temporary) / "snapshot.sqlite3"
            if raw.is_file():
                if raw.stat().st_size > MAX_BYTES:
                    raise ValueError("journal too large")
                snapshot_read_only(raw, copy)
            else:
                encoded = self.directory / (binding.sha256 + ".b64")
                with encoded.open("rb") as f:
                    payload = f.read(4 * ((MAX_BYTES + 2) // 3) + 2)
                    if f.read(1):
                        raise ValueError("encoded journal too large")
                copy.write_bytes(base64.b64decode(payload.strip(), validate=True))
            if copy.stat().st_size > MAX_BYTES or hashlib.sha256(copy.read_bytes()).hexdigest() != binding.sha256:
                raise ValueError("stopped file differs from the operator checkpoint")
            with closing(sqlite3.connect(copy.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
                db.execute("PRAGMA trusted_schema=OFF")
                result = inspect_journal(db)
                if result["account"] != binding.account:
                    raise PermissionError("tenant guard mismatch")
                if (result["events"] != binding.sequence or result["head"] != binding.head or
                        result["checkpoint"] == "AUTHORITY_REQUIRED" or
                        (result["profile"] or {}).get("market", COINBASE_MARKET.name) != COINBASE_MARKET.name):
                    raise ValueError("incompatible journal or checkpoint")
                db.row_factory = sqlite3.Row
                fills = []
                for row in db.execute("SELECT payload FROM events ORDER BY seq"):
                    event = json.loads(row["payload"])
                    details = event.get("details") or {}
                    if event["symbol"] not in PRODUCTS or details.get("source") not in (None, SOURCE):
                        raise ValueError("unsupported quote provenance")
                    fills.append({**{k: event.get(k) for k in ("seq", "order_id", "symbol", "side",
                                                               "quantity", "price", "fee")},
                                  "filled_at": details.get("filled_at"), "source": details.get("source")})
                orders = None
                if "paper_orders" in journal_tables(db):
                    orders = [dict(row) for row in db.execute(
                        "SELECT order_id,status,remaining,updated_at FROM paper_orders ORDER BY rowid DESC")]
                reason, = db.execute("SELECT reason FROM paper_guard WHERE id=1").fetchone()
        public = {k: result[k] for k in ("cash_usd", "fees_usd", "realised_usd", "nav_usd",
                                         "unrealised_usd", "positions", "valuation", "events", "head")}
        return ({**public, "source": "verified_stopped_sqlite_journal", "execution": "disabled",
                 "captured_at": binding.captured_at, "sha256": binding.sha256,
                 "recorded_risk": reason, "recorded_armed": bool(result["stored_armed_flag"])}, fills, orders)
