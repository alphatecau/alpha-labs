"""Single-owner spot paper session backed by the existing transactional journal."""
import fcntl
import json
import re
import sqlite3
from collections import defaultdict, deque
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from hashlib import sha256
from pathlib import Path
from threading import RLock

from alpha_lab.research.live_paper_quotes import simulated_fill_estimate
from alpha_lab.research.paper_accounting import reconcile_paper_pnl
from alpha_lab.research.paper_checkpoint import read_state_checkpoint
from alpha_lab.research.paper_journal import LOCAL_TABLES, journal_tables
from alpha_lab.research.paper_market import COINBASE_MARKET, DEFAULT_COSTS, PaperCosts, PaperMarket
from alpha_lab.research.paper_risk import PaperRiskLimits, authorise_simulated_order
from alpha_lab.research.paper_runtime import PaperRuntime

LIMITS = PaperRiskLimits()
RISK_POLICY_VERSION = 2
ZERO = Decimal("0")
_DECIMAL = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,8})?")
_ORDER_ID = re.compile(r"[A-Za-z0-9_-]{16,80}")
_ACCOUNT_ID = re.compile(r"[A-Za-z0-9_-]{16,80}")
MAX_PENDING = 20
OPEN_ORDERS = ("PENDING", "PARTIALLY_FILLED")


class PaperRejection(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


@dataclass(frozen=True)
class OrderIntent:
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    stop: Decimal | None
    limit: Decimal | None
    fingerprint: str

    def terms(self):
        return {"symbol": self.symbol, "side": self.side, "quantity": str(self.quantity),
                "stop": str(self.stop) if self.stop is not None else None,
                "limit": str(self.limit) if self.limit is not None else None}


def parse_order(payload, products=COINBASE_MARKET.symbols):
    if not isinstance(payload, dict):
        raise PaperRejection("INVALID_ORDER", "Order must be a JSON object", 400)
    order_id, symbol, side = (payload.get(k) for k in ("order_id", "symbol", "side"))
    base_keys = {"order_id", "symbol", "side", "quantity"}
    expected = base_keys | {"stop_price"} if side == "BUY" else base_keys
    if payload.get("order_type") == "LIMIT":
        expected |= {"order_type", "limit_price"}
    if (set(payload) != expected or symbol not in products or side not in ("BUY", "SELL")
            or not isinstance(order_id, str) or not _ORDER_ID.fullmatch(order_id)
            or order_id.startswith(("stop_", "limit_"))):
        raise PaperRejection("INVALID_ORDER", "Invalid order fields", 400)

    def value(key):
        raw = payload[key]
        if not isinstance(raw, str) or not _DECIMAL.fullmatch(raw) or Decimal(raw) <= 0:
            raise PaperRejection("INVALID_ORDER", f"Invalid {key}", 400)
        return Decimal(raw).normalize()

    quantity = value("quantity")
    stop = value("stop_price") if side == "BUY" else None
    limit = value("limit_price") if "limit_price" in payload else None
    if stop is not None and limit is not None and stop >= limit:
        raise PaperRejection("INVALID_STOP", "Buy stop must be below the limit", 400)
    terms = f"{symbol}\n{side}\n{quantity}\n{stop}"
    if limit is not None:
        terms += f"\nLIMIT\n{limit}"
    return OrderIntent(order_id, symbol, side, quantity, stop, limit, sha256(terms.encode()).hexdigest())


class LivePaperSession:
    def __init__(self, directory, account_id, feed, *, clock=lambda: datetime.now(timezone.utc),
                 checkpoint_store=None, provision=False, market=COINBASE_MARKET, costs=DEFAULT_COSTS,
                 migrate=True):
        if not isinstance(account_id, str) or not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("explicit paper account binding required")
        if checkpoint_store is not None and checkpoint_store.owner_id != account_id:
            raise ValueError("checkpoint authority owner mismatch")
        if type(provision) is not bool or (provision and checkpoint_store is None):
            raise ValueError("explicit protected genesis requires an independent checkpoint authority")
        if not isinstance(market, PaperMarket) or not isinstance(costs, PaperCosts):
            raise ValueError("explicit paper market and cost policy required")
        self.market, self.costs = market, costs
        self.feed, self.clock = feed, clock
        self.owner_id = account_id
        self.checkpoint_store = checkpoint_store
        self._last_checkpoint = None
        self._armed_session = None
        self.lock = RLock()
        self.fault = False
        self.file_lock = (Path(directory) / "alpha-paper.lock").open("a+b")
        self.runtime = None
        try:
            fcntl.flock(self.file_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            path = Path(directory) / "alpha-paper.sqlite3"
            if checkpoint_store is not None:
                envelope = checkpoint_store.load()
                if provision and (envelope is not None or path.exists()):
                    raise ValueError("protected genesis requires a new journal and empty authority: HALT")
                if not provision and (envelope is None or not path.is_file()):
                    raise ValueError("protected journal or checkpoint missing: HALT")
            self.runtime = PaperRuntime(path, check_same_thread=False,
                                        migrate=provision or (checkpoint_store is None and migrate))
            self.db = self.runtime.journal.connection
            self.db.row_factory = sqlite3.Row
            if checkpoint_store is None:
                with self.runtime.journal.transaction():
                    tables = journal_tables(self.db)
                    if "paper_state_sequence" in tables:
                        raise ValueError("protected journal cannot be opened without its authority: HALT")
                    if not migrate and not LOCAL_TABLES <= tables:
                        raise ValueError("journal schema requires a verified working copy: HALT")
                    self._open_account(account_id, migrate=migrate)
            elif provision:
                with self.runtime.journal.transaction():
                    self._open_account(account_id)
                    self.db.execute("CREATE TABLE paper_state_sequence (id INTEGER PRIMARY KEY CHECK (id=1), "
                                    "sequence INTEGER NOT NULL CHECK (sequence>=0))")
                    self.db.execute("INSERT INTO paper_state_sequence VALUES (1, 0)")
                    genesis = self._state_commitment()
                self._record_checkpoint(genesis, (None, None))
            else:
                self._last_checkpoint = self._verify_checkpoint()
                with self._operation():
                    if self._guard()["enabled"]:
                        self._set_control(False, "STARTUP_HALTED")
        except Exception:
            if self.runtime is not None:
                self.runtime.close()
            self.file_lock.close()
            raise

    def _open_account(self, account_id, *, migrate=True):
        if migrate:
            self._create_control_tables()
        row = self.db.execute("SELECT account FROM paper_guard WHERE id = 1").fetchone()
        config = self.db.execute("SELECT configuration FROM paper_configuration WHERE id=1").fetchone()
        expected = self._configuration()
        if config is None:
            if not migrate:
                raise ValueError("paper journal configuration missing: HALT")
            if row is not None and (self.market is not COINBASE_MARKET or self.costs != DEFAULT_COSTS):
                raise ValueError("legacy journal requires its original Coinbase market and cost policy")
            self.db.execute("INSERT INTO paper_configuration VALUES (1,?)", (expected,))
        elif config["configuration"] != expected:
            raise ValueError("journal market or cost policy mismatch")
        if row is None:
            if not migrate or self.runtime.events:
                raise ValueError("paper journal missing its owner binding")
            initial = str(self.runtime.ledger.starting_cash)
            self.db.execute("INSERT INTO paper_guard VALUES (1, ?, 0, 'STARTUP_HALTED', '', ?, ?, ?, '', 0)",
                            (account_id, initial, initial, initial))
        elif row["account"] != account_id:
            raise ValueError("paper journal owner mismatch")
        else:
            self.db.execute("UPDATE paper_guard SET enabled = 0, reason = 'STARTUP_HALTED', revision = revision + 1 "
                            "WHERE id = 1 AND enabled = 1")

    def _create_control_tables(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS paper_guard (
            id INTEGER PRIMARY KEY CHECK (id = 1), account TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK (enabled IN (0,1)), reason TEXT NOT NULL,
            day TEXT NOT NULL, day_start TEXT NOT NULL, peak TEXT NOT NULL,
            last_nav TEXT NOT NULL, daily_breach TEXT NOT NULL, revision INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS relay_nonces (
            nonce TEXT PRIMARY KEY, received INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS paper_orders (
            order_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, terms TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('PENDING','PARTIALLY_FILLED','FILLED','CANCELLED','REJECTED')),
            remaining TEXT NOT NULL, reason TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS paper_order_history (
            sequence INTEGER PRIMARY KEY, order_id TEXT NOT NULL, terms TEXT NOT NULL,
            status TEXT NOT NULL, reason TEXT NOT NULL, occurred_at TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS paper_configuration (
            id INTEGER PRIMARY KEY CHECK (id=1), configuration TEXT NOT NULL)""")

    def close(self):
        with self.lock:
            self.runtime.close()
            self.file_lock.close()

    def claim_request(self, nonce, now):
        with self._operation(), self._write_context():
            self.db.execute("DELETE FROM relay_nonces WHERE received <= ?", (now - 60,))
            if self.db.execute("SELECT 1 FROM relay_nonces WHERE nonce = ?", (nonce,)).fetchone():
                raise PaperRejection("INVALID_RELAY", "Request already used", 401)
            if self.db.execute("SELECT COUNT(*) FROM relay_nonces").fetchone()[0] >= 120:
                raise PaperRejection("RATE_LIMITED", "Paper request limit reached", 429)
            self.db.execute("INSERT INTO relay_nonces VALUES (?, ?)", (nonce, now))

    def _guard(self):
        row = self.db.execute("SELECT * FROM paper_guard WHERE id = 1").fetchone()
        if row is None:
            raise ValueError("paper control record missing")
        return row

    def _set_control(self, enabled, reason):
        if not enabled:
            self.runtime.ledger.halt()
        with self._write_context():
            updated = self.db.execute("UPDATE paper_guard SET enabled = ?, reason = ?, revision = revision + 1 WHERE id = 1",
                                      (int(enabled), reason))
            if updated.rowcount != 1:
                raise ValueError("paper control record missing")
        if enabled:
            self.runtime.enable(operator_approved=True)

    def _write_context(self):
        return nullcontext() if self.db.in_transaction else self.db

    def fail_closed(self):
        with self.lock:
            self.fault = True
            self._armed_session = None
            self.runtime.ledger.halt()
            if self.checkpoint_store is None:
                try:
                    self._set_control(False, "LEDGER_HALT")
                except (sqlite3.Error, ValueError):
                    pass

    def _state_commitment(self):
        versions = self.db.execute("SELECT id,sequence FROM paper_state_sequence").fetchall()
        if len(versions) != 1 or versions[0]["id"] != 1:
            raise ValueError("protected state sequence missing or inconsistent: HALT")
        sequence = versions[0]["sequence"]
        guard = dict(self._guard())
        if guard["account"] != self.owner_id or self.db.execute("SELECT COUNT(*) FROM paper_guard").fetchone()[0] != 1:
            raise ValueError("paper journal owner mismatch: HALT")
        journal_head = self.runtime.journal.verify()
        count, = self.db.execute("SELECT COUNT(*) FROM events").fetchone()
        if (count, journal_head) != (self.runtime.ledger.sequence, self.runtime.journal_head):
            raise ValueError("journal and active ledger disagree: HALT")
        config = self.db.execute("SELECT * FROM paper_configuration").fetchall()
        if len(config) != 1 or tuple(config[0]) != (1, self._configuration()):
            raise ValueError("protected journal configuration mismatch: HALT")
        state = {
            "sequence": sequence, "guard": guard, "journal": [count, journal_head],
            "relay_nonces": [tuple(row) for row in self.db.execute("SELECT * FROM relay_nonces ORDER BY nonce")],
            "orders": [tuple(row) for row in self.db.execute("SELECT * FROM paper_orders ORDER BY rowid")],
            "order_history": [tuple(row) for row in self.db.execute("SELECT * FROM paper_order_history ORDER BY sequence")],
            "schema": [tuple(row) for row in self.db.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*' ORDER BY name")],
            "policy_version": RISK_POLICY_VERSION,
            "limits": {key: str(value) for key, value in asdict(LIMITS).items()},
            "starting_cash": str(self.runtime.ledger.starting_cash), "currency": "USD",
            "configuration": tuple(config[0]),
        }
        digest = sha256(json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        return sequence, digest

    def _configuration(self):
        return json.dumps({"market": self.market.name, "products": self.market.symbols,
                           "quantity_step": str(self.market.quantity_step), "currency": "USD",
                           "fee": str(self.costs.fee.normalize()),
                           "slippage": str(self.costs.slippage.normalize())}, sort_keys=True)

    def _verify_checkpoint(self):
        store = self.checkpoint_store
        try:
            trusted = read_state_checkpoint(store.load(), owner=self.owner_id, secret=store.verification_key)
            if (trusted != self._state_commitment()
                    or self._last_checkpoint is not None and trusted != self._last_checkpoint):
                raise ValueError("protected state checkpoint mismatch: HALT")
            return trusted
        except Exception as exc:
            raise ValueError("protected state checkpoint mismatch or authority unavailable: HALT") from exc

    def _record_checkpoint(self, current, previous):
        store = self.checkpoint_store
        envelope = store.record(sequence=current[0], head=current[1],
                                expected_sequence=previous[0], expected_head=previous[1])
        if read_state_checkpoint(envelope, owner=self.owner_id, secret=store.verification_key) != current:
            raise ValueError("checkpoint commit confirmation mismatch: HALT")
        self._last_checkpoint = current

    @contextmanager
    def _operation(self):
        with self.lock:
            protected = self.checkpoint_store is not None
            if protected and self.fault:
                raise PaperRejection("CHECKPOINT_HALT", "Protected paper state requires recovery", 503)
            rejection = None
            current = None
            try:
                with self.runtime.journal.transaction():
                    previous = self._verify_checkpoint() if protected else None
                    changes = self.db.total_changes
                    try:
                        yield
                    except PaperRejection as exc:
                        rejection = exc
                    if protected and self.db.total_changes != changes:
                        self.db.execute("UPDATE paper_state_sequence SET sequence=sequence+1 WHERE id=1")
                        current = self._state_commitment()
                if current is not None:
                    self._record_checkpoint(current, previous)
            except Exception as exc:
                # SQLite and PostgreSQL commit separately. An unmatched local
                # commit is never acknowledged or adopted at the next startup.
                self.fail_closed()
                if not protected:
                    raise
                raise PaperRejection("CHECKPOINT_HALT", "Protected paper state requires recovery", 503) from exc
            if rejection is not None:
                raise rejection

    def _account(self, marks):
        ledger = self.runtime.ledger
        account = reconcile_paper_pnl(ledger.fills, marks, starting_cash=ledger.starting_cash)
        expected_positions = {k: v for k, v in ledger.positions.items() if v}
        actual_positions = {k: v for k, v in account["positions"].items() if v}
        if account["cash"] != ledger.cash or actual_positions != expected_positions or account["nav"] != ledger.nav(marks):
            raise ValueError("independent reconciliation mismatch")
        return account

    def _refresh(self, now, quotes, healthy):
        guard = self._guard()
        if self.fault:
            raise PaperRejection("LEDGER_HALT", "Ledger requires recovery", 503)
        symbols = set(self.market.symbols)
        seen = set()
        for fill in reversed(self.runtime.events):
            symbol = fill["symbol"]
            if symbol in seen or symbol not in quotes:
                continue
            seen.add(symbol)
            details, quote = fill["details"], quotes[symbol]
            if (not self.market.accepts(quote, now) or quote.source != details["source"]
                    or quote.source_sequence < details["source_sequence"]
                    or quote.exchange_at < datetime.fromisoformat(details["source_time"])
                    or quote.source_sequence == details["source_sequence"] and details.get("book") is not None
                    and details["book"] != self._book_terms(quote)):
                healthy[symbol] = False
            if seen == symbols:
                break
        if (set(quotes) != symbols or set(healthy) != symbols
                or not all(healthy[s] is True and quotes[s].symbol == s
                           and self.market.accepts(quotes[s], now) for s in symbols)):
            if guard["enabled"]:
                self._set_control(False, "MARKET_DATA_HALT")
            return None
        # An accepted transport clock skew never authorises a noncausal mark or
        # fill. Retain the book while the local clock catches up.
        future = {symbol for symbol, quote in quotes.items() if quote.exchange_at > now}
        if future:
            healthy.update(dict.fromkeys(future, False))
            return None
        marks = {symbol: quote.bid for symbol, quote in quotes.items()}
        account = self._account(marks)
        nav = account["nav"]
        day = now.date().isoformat()
        day_start, peak, last_nav = (Decimal(guard[key]) for key in ("day_start", "peak", "last_nav"))
        if not all(v.is_finite() and v > 0 for v in (day_start, peak, last_nav, nav)):
            raise ValueError("invalid durable risk state")
        if guard["day"] and day < guard["day"]:
            raise ValueError("UTC risk clock moved backwards")
        # Carry the last observed NAV across midnight, conservatively using
        # the higher sample when the exact midnight mark is unavailable.
        if guard["day"] != day:
            day_start = max(last_nav, nav)
        peak = max(peak, nav)
        daily_breach = guard["daily_breach"]
        if day_start - nav >= day_start * LIMITS.daily_loss_halt_pct:
            daily_breach = day
        old = (guard["day"], guard["day_start"], guard["peak"], guard["last_nav"], guard["daily_breach"])
        new = (day, str(day_start), str(peak), str(nav), daily_breach)
        if new != old:
            with self._write_context():
                self.db.execute("UPDATE paper_guard SET day=?, day_start=?, peak=?, last_nav=?, daily_breach=? WHERE id=1", new)
        if daily_breach == day and (guard["enabled"] or guard["reason"] != "DAILY_LOSS_HALT"):
            self._set_control(False, "DAILY_LOSS_HALT")
        elif (daily_breach != day and peak - nav >= peak * LIMITS.drawdown_halt_pct
              and (guard["enabled"] or guard["reason"] != "DRAWDOWN_HALT")):
            self._set_control(False, "DRAWDOWN_HALT")
        return account

    def _lots(self):
        lots = defaultdict(deque)
        for fill in self.runtime.events:
            symbol, qty = fill["symbol"], Decimal(fill["quantity"])
            if fill["side"] == "BUY":
                stop = Decimal(fill["details"]["stop_price"])
                if not stop.is_finite() or stop <= 0 or symbol not in self.market.symbols:
                    raise ValueError("paper lot stop metadata invalid")
                lots[symbol].append([qty, stop])
                continue
            while qty:
                lot = lots[symbol][0]
                used = min(qty, lot[0])
                qty -= used
                lot[0] -= used
                if not lot[0]:
                    lots[symbol].popleft()
        return lots

    def _net_stop(self, stop):
        return stop * (1 - self.costs.slippage) * (1 - self.costs.fee)

    def _open_risk(self, lots, quotes):
        return sum((quantity * max(ZERO, quotes[symbol].bid - self._net_stop(stop))
                    for symbol, queue in lots.items() for quantity, stop in queue), ZERO)

    def _depth(self, quote, side):
        size = quote.ask_size if side == "BUY" else quote.bid_size
        used = ZERO
        for fill in self.runtime.events:
            if fill["symbol"] != quote.symbol or fill["details"]["source_sequence"] != quote.source_sequence:
                continue
            if fill["details"].get("book") != self._book_terms(quote):
                # A pre-upgrade fill does not attest to the original displayed depth.
                return ZERO
            if fill["side"] == side:
                used += Decimal(fill["quantity"])
        return max(ZERO, size - used)

    def control(self, action, *, expected_revision=None):
        with self._operation():
            if action not in ("arm", "halt"):
                raise PaperRejection("INVALID_CONTROL", "Unknown paper control", 400)
            if action == "halt":
                self._set_control(False, "OPERATOR_HALT")
                return {"armed": False, "reason": "OPERATOR_HALT"}
            now = self.clock()
            quotes, healthy, _ = self.feed.snapshot(now)
            account = self._refresh(now, quotes, healthy)
            guard = self._guard()
            if account is None:
                raise PaperRejection("MARKET_DATA_HALT", "Fresh books for all configured markets are required")
            if type(expected_revision) is not int or expected_revision != guard["revision"]:
                raise PaperRejection("CONTROL_CHANGED", "Paper control changed. Refresh before arming.")
            if not self._can_arm(guard, account):
                raise PaperRejection("LOSS_HALT", "A portfolio loss limit is active")
            self._lots()
            self._set_control(True, "ARMED")
            return {"armed": True, "reason": "ARMED"}

    @staticmethod
    def _can_arm(guard, account):
        peak = Decimal(guard["peak"])
        return (account is not None and guard["daily_breach"] != guard["day"]
                and peak - account["nav"] < peak * LIMITS.drawdown_halt_pct)

    def order(self, payload):
        order = parse_order(payload, self.market.symbols)
        if order.quantity % self.market.quantity_step:
            raise PaperRejection("INVALID_ORDER", "Quantity must match the instrument increment", 400)
        with self._operation():
            existing = self._order_record(order.order_id)
            if existing is not None:
                if existing["fingerprint"] != order.fingerprint:
                    raise PaperRejection("IDEMPOTENCY_CONFLICT", "Order ID is already bound to different terms")
                return self._order_result(existing)
            if order.order_id in self.runtime.order_ids:
                fill = next(event for event in self.runtime.events if event["order_id"] == order.order_id)
                if fill["details"]["fingerprint"] != order.fingerprint:
                    raise PaperRejection("IDEMPOTENCY_CONFLICT", "Order ID is already bound to different terms")
                return {"status": "ALREADY_COMMITTED", "fill": fill}
            now = self.clock()
            quotes, healthy, _ = self.feed.snapshot(now)
            account = self._refresh(now, quotes, healthy)
            try:
                if account is None:
                    raise PaperRejection("MARKET_DATA_HALT", "Fresh books for all configured markets are required")
                if order.limit is not None:
                    return self._submit_limit(order, now, quotes, account)
                fill = self._fill(order.order_id, quotes[order.symbol], order.side, order.quantity, order.stop,
                                  order.fingerprint, "manual", now, quotes, account)
            except PaperRejection as exc:
                self._audit_order(order.order_id, order.terms(), "REJECTED", exc.code, now)
                raise
            self._audit_order(order.order_id, order.terms(), "FILLED", "", now)
            return {"status": "SIMULATED_FILL", "fill": fill}

    def _audit_order(self, order_id, terms, status, reason, now):
        self.db.execute("INSERT INTO paper_order_history(order_id,terms,status,reason,occurred_at) VALUES(?,?,?,?,?)",
                        (order_id, json.dumps(terms, sort_keys=True), status, reason, now.isoformat()))

    def _order_record(self, order_id):
        return self.db.execute("SELECT * FROM paper_orders WHERE order_id=?", (order_id,)).fetchone()

    @staticmethod
    def _order_result(row):
        return {"status": row["status"], "order": {**json.loads(row["terms"]), "order_id": row["order_id"],
                "status": row["status"], "remaining": row["remaining"], "reason": row["reason"]}}

    def _transition_order(self, row, status, remaining, reason, now):
        self.db.execute("UPDATE paper_orders SET status=?,remaining=?,reason=?,updated_at=? WHERE order_id=?",
                        (status, str(remaining), reason, now.isoformat(), row["order_id"]))
        self._audit_order(row["order_id"], json.loads(row["terms"]), status, reason, now)
        return self._order_record(row["order_id"])

    def _submit_limit(self, order, now, quotes, account):
        guard = self._guard()
        if not guard["enabled"] or self.runtime.ledger.halted:
            raise PaperRejection(guard["reason"], "Paper execution is halted")
        pending = self.db.execute("SELECT COUNT(*) FROM paper_orders WHERE status IN (?,?)", OPEN_ORDERS).fetchone()[0]
        if pending >= MAX_PENDING:
            raise PaperRejection("PENDING_ORDER_LIMIT", "Maximum number of open simulated orders reached", 429)
        self.db.execute("INSERT INTO paper_orders VALUES (?,?,?,'PENDING',?,'',?)",
                        (order.order_id, order.fingerprint, json.dumps(order.terms(), sort_keys=True),
                         str(order.quantity), now.isoformat()))
        self._audit_order(order.order_id, order.terms(), "PENDING", "", now)
        row = self._match_limit(self._order_record(order.order_id), now, quotes, account)
        return self._order_result(row)

    def _match_limit(self, row, now, quotes, account):
        terms = json.loads(row["terms"])
        quote, side = quotes[terms["symbol"]], terms["side"]
        limit = Decimal(terms["limit"])
        stop = Decimal(terms["stop"]) if terms["stop"] is not None else None
        remaining = Decimal(row["remaining"])
        if side == "BUY" and Decimal(terms["quantity"]) * (limit * (1 + self.costs.fee) - self._net_stop(stop)) > (
                account["nav"] * LIMITS.max_position_risk_pct):
            return self._transition_order(row, "REJECTED", remaining, "POSITION_RISK_EXCEEDED", now)
        quantity = min(remaining, self._depth(quote, side)).quantize(self.market.quantity_step, rounding=ROUND_DOWN)
        if not quantity:
            return row
        estimate = simulated_fill_estimate(quote, side=side, quantity=quantity, fee_rate=self.costs.fee,
                                           slippage_bps=self.costs.slippage * 10000)
        price = Decimal(estimate["executed_price"])
        if (side == "BUY" and price > limit) or (side == "SELL" and price < limit):
            return row
        child = sha256(f"{row['order_id']}:{self.runtime.ledger.sequence}".encode()).hexdigest()[:40]
        try:
            self._fill("limit_" + child, quote, side, quantity, stop, row["fingerprint"], "limit",
                       now, quotes, account, parent_order_id=row["order_id"])
        except PaperRejection as exc:
            if exc.code in ("QUOTE_CHANGED", "MARKET_DATA_HALT", "RISK_HALT"):
                return row
            return self._transition_order(row, "REJECTED", remaining, exc.code, now)
        remaining -= quantity
        return self._transition_order(row, "PARTIALLY_FILLED" if remaining else "FILLED", remaining, "", now)

    def cancel(self, payload):
        order_id = payload.get("order_id") if isinstance(payload, dict) and set(payload) == {"order_id"} else None
        if not isinstance(order_id, str) or not _ORDER_ID.fullmatch(order_id):
            raise PaperRejection("INVALID_ORDER", "Valid pending order ID required", 400)
        with self._operation():
            row = self._order_record(order_id)
            if row is None:
                raise PaperRejection("UNKNOWN_ORDER", "Order is unavailable")
            if row["status"] == "CANCELLED":
                return self._order_result(row)
            if row["status"] not in OPEN_ORDERS:
                raise PaperRejection("ORDER_TERMINAL", "Order has no cancellable remainder")
            return self._order_result(self._transition_order(
                row, "CANCELLED", row["remaining"], "OPERATOR_CANCEL", self.clock()))

    def _fill(self, order_id, quote, side, quantity, stop, fingerprint, origin, now, quotes, account,
              *, parent_order_id=None):
        guard = self._guard()
        if not guard["enabled"] or self.runtime.ledger.halted:
            raise PaperRejection(guard["reason"], "Paper execution is halted")
        if quantity > self._depth(quote, side):
            raise PaperRejection("INSUFFICIENT_DEPTH", "Quantity exceeds remaining displayed top-of-book liquidity")
        if side == "SELL" and quantity > account["positions"].get(quote.symbol, ZERO):
            raise PaperRejection("INSUFFICIENT_POSITION", "Sell quantity exceeds the paper position")
        if side == "BUY" and (stop is None or stop >= quote.bid):
            raise PaperRejection("INVALID_STOP", "A protective stop below the current bid is required", 400)

        estimate = simulated_fill_estimate(quote, side=side, quantity=quantity, fee_rate=self.costs.fee,
                                           slippage_bps=self.costs.slippage * 10000)
        price, fee = Decimal(estimate["executed_price"]), Decimal(estimate["fee"])
        marks = {symbol: item.bid for symbol, item in quotes.items()}
        gross = account["nav"] - account["cash"]
        aggregate = self._open_risk(self._lots(), quotes)
        loss = quantity * (price - self._net_stop(stop)) + fee if side == "BUY" else ZERO
        peak, day_start = Decimal(guard["peak"]), Decimal(guard["day_start"])
        if side == "BUY":
            cost = quantity * price + fee
            if cost > account["cash"]:
                raise PaperRejection("INSUFFICIENT_CASH", "Order exceeds available virtual cash")
            nav_after_cost = account["nav"] - cost + quantity * quote.bid
            decision = authorise_simulated_order(
                nav=nav_after_cost, initial_nav=self.runtime.ledger.starting_cash,
                peak_nav=peak, day_start_nav=day_start, proposed_loss=loss,
                aggregate_open_risk=aggregate, gross_notional=gross,
                proposed_notional=quantity * quote.bid, data_fresh=True,
                ledger_reconciled=True, operator_enabled=True)
            if not decision["approved"]:
                raise PaperRejection("RISK_REJECTED", ", ".join(decision["reasons"]))
        now = self.clock()
        current, healthy, _ = self.feed.snapshot(now)
        if (set(current) != set(quotes) or set(healthy) != set(quotes)
                or not all(healthy[symbol] is True and self.market.accepts(current[symbol], now)
                           for symbol in quotes)):
            self._set_control(False, "MARKET_DATA_HALT")
            raise PaperRejection("MARKET_DATA_HALT", "Market data became unavailable before fill")
        if not all(item.exchange_at <= now and self.market.accepts(item, now)
                   and self._same_book(current[symbol], item) for symbol, item in quotes.items()):
            raise PaperRejection("QUOTE_CHANGED", "The market snapshot changed. Retry with fresh quotes.")
        details = {
            "origin": origin, "fingerprint": fingerprint, "stop_price": str(stop) if stop is not None else None,
            "planned_stop_loss": str(loss), "source": quote.source, "source_time": quote.source_timestamp,
            "source_sequence": quote.source_sequence, "received_at": quote.observed_at.isoformat(),
            "filled_at": now.isoformat(), "book": self._book_terms(quote),
        }
        if parent_order_id is not None:
            details["parent_order_id"] = parent_order_id
        try:
            self.runtime.execute(symbol=quote.symbol, side=side, quantity=quantity, reference_mid=quote.mid,
                                 executed_price=price, fee=fee, quote_timestamp=quote.exchange_at, now=now,
                                 marks=marks, proposed_loss=loss, aggregate_open_risk=aggregate,
                                 gross_notional=gross, peak_nav=peak, day_start_nav=day_start,
                                 operator_approved=True, order_id=order_id, details=details)
        except PermissionError as exc:
            self._set_control(False, "RISK_HALT")
            raise PaperRejection("RISK_HALT", str(exc)) from exc
        self._refresh(now, quotes, dict.fromkeys(self.market.symbols, True))
        return self.runtime.events[-1]

    @staticmethod
    def _book_terms(quote):
        return [str(value.normalize()) for value in (quote.bid, quote.ask, quote.bid_size, quote.ask_size)]

    @staticmethod
    def _same_book(left, right):
        fields = ("symbol", "source", "source_sequence", "source_timestamp", "bid", "ask", "bid_size", "ask_size")
        return all(getattr(left, field) == getattr(right, field) for field in fields)

    def on_market_update(self):
        try:
            with self._operation():
                now = self.clock()
                quotes, healthy, _ = self.feed.snapshot(now)
                account = self._refresh(now, quotes, healthy)
                if account is None or not self._guard()["enabled"]:
                    return
                for symbol, lots in self._lots().items():
                    quote = quotes[symbol]
                    if lots and any(quote.bid <= stop for _, stop in lots):
                        quantity = min(account["positions"][symbol], self._depth(quote, "SELL"))
                        quantity = quantity.quantize(self.market.quantity_step, rounding=ROUND_DOWN)
                        if quantity:
                            key = f"{symbol}:{quote.source_sequence}:{self.runtime.ledger.sequence}"
                            order_id = "stop_" + sha256(key.encode()).hexdigest()[:32]
                            self._fill(order_id, quote, "SELL", quantity, None, None,
                                       "protective_stop", now, quotes, account)
                            account = self._account({s: q.bid for s, q in quotes.items()})
                for row in self.db.execute("SELECT * FROM paper_orders WHERE status IN (?,?) ORDER BY rowid",
                                           OPEN_ORDERS).fetchall():
                    if self.runtime.ledger.halted:
                        break
                    self._match_limit(row, now, quotes, account)
                    account = self._account({s: q.bid for s, q in quotes.items()})
        except PaperRejection:
            return
        except Exception:
            self.fail_closed()

    def state(self):
        with self.lock:
            with self._operation():
                result = self._state()
            result["recovery"] = {"status": "VERIFIED" if self._last_checkpoint else "LOCAL_UNANCHORED",
                                  "checkpoint_sequence": self._last_checkpoint[0] if self._last_checkpoint else None,
                                  "journal_sequence": self.runtime.ledger.sequence}
            return result

    def checkpoint_history(self):
        if self.checkpoint_store is None:
            raise PaperRejection("CHECKPOINT_HALT", "Protected checkpoint authority required", 503)
        with self._operation():
            rows = self.checkpoint_store.history()
            if (rows[0]["sequence"], rows[0]["head"]) != self._last_checkpoint:
                raise ValueError("checkpoint history and active ledger disagree: HALT")
            return {"checkpoints": rows}

    def _state(self):
        now = self.clock()
        quotes, healthy, history = self.feed.snapshot(now)
        account = self._refresh(now, quotes, healthy)
        guard = self._guard()
        portfolio = {"cash": str(self.runtime.ledger.cash),
                     "positions": {s: str(q) for s, q in self.runtime.ledger.positions.items() if q},
                     "reconciled": account is not None}
        if account is not None:
            portfolio.update({key: str(account[key]) for key in ("nav", "fees", "realised", "unrealised")})
            portfolio["cost_basis"] = {symbol: str(value) for symbol, value in account["cost_basis"].items()}
            portfolio["aggregate_stop_risk"] = str(self._open_risk(self._lots(), quotes))
        return {
            "mode": "SIMULATION_ONLY", "currency": "USD", "autonomous": False,
            "market_profile": self.market.name, "execution_costs": {
                "fee_bps": str(self.costs.fee * 10000), "slippage_bps": str(self.costs.slippage * 10000)},
            "server_time": now.isoformat(),
            "market": {s: {"healthy": healthy.get(s) is True, "source": q.source, "source_time": q.source_timestamp,
                           "age_seconds": round((now - q.exchange_at).total_seconds(), 2),
                           "bid": str(q.bid), "ask": str(q.ask), "bid_size": str(q.bid_size),
                           "ask_size": str(q.ask_size)} for s, q in quotes.items()},
            "history": history, "portfolio": portfolio,
            "risk": {"armed": bool(guard["enabled"]), "reason": guard["reason"],
                     "can_arm": self._can_arm(guard, account), "revision": guard["revision"],
                     "day_start_nav": guard["day_start"], "peak_nav": guard["peak"],
                     "data_healthy": account is not None},
            "fills": list(reversed(self.runtime.events[-30:])),
            "orders": [self._order_result(row)["order"] for row in self.db.execute(
                "SELECT * FROM paper_orders ORDER BY status IN ('PENDING','PARTIALLY_FILLED') DESC, rowid DESC LIMIT 30")],
            "order_history": [dict(row) for row in self.db.execute(
                "SELECT sequence,order_id,status,reason,occurred_at FROM paper_order_history ORDER BY sequence DESC LIMIT 30")],
        }
