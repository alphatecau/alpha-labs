"""Single-owner spot paper session backed by the existing transactional journal."""
import fcntl
import json
import re
import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from hashlib import sha256
from pathlib import Path
from threading import RLock

from alpha_lab.research.coinbase_paper_book import PRODUCTS, executable
from alpha_lab.research.live_paper_quotes import simulated_fill_estimate
from alpha_lab.research.paper_accounting import reconcile_paper_pnl
from alpha_lab.research.paper_risk import PaperRiskLimits, authorise_simulated_order
from alpha_lab.research.paper_runtime import PaperRuntime

LIMITS = PaperRiskLimits()
FEE = Decimal("0.001")
SLIPPAGE = Decimal("0.0005")
ZERO = Decimal("0")
UNIT = Decimal("0.00000001")
_DECIMAL = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,8})?")
_ORDER_ID = re.compile(r"[A-Za-z0-9_-]{16,80}")
_ACCOUNT_ID = re.compile(r"[A-Za-z0-9_-]{16,80}")


class PaperRejection(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


def parse_order(payload):
    if not isinstance(payload, dict):
        raise PaperRejection("INVALID_ORDER", "Order must be a JSON object", 400)
    order_id, symbol, side = (payload.get(k) for k in ("order_id", "symbol", "side"))
    base_keys = {"order_id", "symbol", "side", "quantity"}
    expected = base_keys | {"stop_price"} if side == "BUY" else base_keys
    if (set(payload) != expected or symbol not in PRODUCTS or side not in ("BUY", "SELL")
            or not isinstance(order_id, str) or not _ORDER_ID.fullmatch(order_id)
            or order_id.startswith("stop_")):
        raise PaperRejection("INVALID_ORDER", "Invalid order fields", 400)

    def value(key):
        raw = payload[key]
        if not isinstance(raw, str) or not _DECIMAL.fullmatch(raw) or Decimal(raw) <= 0:
            raise PaperRejection("INVALID_ORDER", f"Invalid {key}", 400)
        return Decimal(raw).normalize()

    quantity = value("quantity")
    stop = value("stop_price") if side == "BUY" else None
    fingerprint = sha256(f"{symbol}\n{side}\n{quantity}\n{stop}".encode()).hexdigest()
    return order_id, symbol, side, quantity, stop, fingerprint


class LivePaperSession:
    def __init__(self, directory, account_id, feed, *, clock=lambda: datetime.now(timezone.utc)):
        if not isinstance(account_id, str) or not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("explicit paper account binding required")
        self.feed, self.clock = feed, clock
        self.lock = RLock()
        self.fault = False
        self.file_lock = (Path(directory) / "alpha-paper.lock").open("a+b")
        self.runtime = None
        try:
            fcntl.flock(self.file_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.runtime = PaperRuntime(Path(directory) / "alpha-paper.sqlite3", check_same_thread=False)
            self.db = self.runtime.journal.connection
            self._open_account(account_id)
        except Exception:
            if self.runtime is not None:
                self.runtime.close()
            self.file_lock.close()
            raise

    def _open_account(self, account_id):
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS paper_guard (
            id INTEGER PRIMARY KEY CHECK (id = 1), account TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK (enabled IN (0,1)), reason TEXT NOT NULL,
            day TEXT NOT NULL, day_start TEXT NOT NULL, peak TEXT NOT NULL,
            last_nav TEXT NOT NULL, daily_breach TEXT NOT NULL, revision INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS relay_nonces (
            nonce TEXT PRIMARY KEY, received INTEGER NOT NULL)""")
        row = self.db.execute("SELECT account FROM paper_guard WHERE id = 1").fetchone()
        if row is None:
            if self.runtime.events:
                raise ValueError("paper journal missing its owner binding")
            initial = str(self.runtime.ledger.starting_cash)
            self.db.execute("INSERT INTO paper_guard VALUES (1, ?, 0, 'STARTUP_HALTED', '', ?, ?, ?, '', 0)",
                            (account_id, initial, initial, initial))
        elif row["account"] != account_id:
            raise ValueError("paper journal owner mismatch")
        else:
            self.db.execute("UPDATE paper_guard SET enabled = 0, reason = 'STARTUP_HALTED', revision = revision + 1 WHERE id = 1")
        self.db.commit()

    def close(self):
        with self.lock:
            self.runtime.close()
            self.file_lock.close()

    def claim_request(self, nonce, now):
        with self.lock, self.db:
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
        with self.db:
            updated = self.db.execute("UPDATE paper_guard SET enabled = ?, reason = ?, revision = revision + 1 WHERE id = 1",
                                      (int(enabled), reason))
            if updated.rowcount != 1:
                raise ValueError("paper control record missing")
        if enabled:
            self.runtime.enable(operator_approved=True)

    def fail_closed(self):
        with self.lock:
            self.fault = True
            self.runtime.ledger.halt()
            try:
                self._set_control(False, "LEDGER_HALT")
            except (sqlite3.Error, ValueError):
                pass

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
        if (set(quotes) != set(PRODUCTS) or set(healthy) != set(PRODUCTS)
                or not all(healthy[s] is True and quotes[s].symbol == s
                           and executable(quotes[s], now) for s in PRODUCTS)):
            if guard["enabled"]:
                self._set_control(False, "MARKET_DATA_HALT")
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
            with self.db:
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
                if not stop.is_finite() or stop <= 0 or symbol not in PRODUCTS:
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

    @staticmethod
    def _net_stop(stop):
        return stop * (1 - SLIPPAGE) * (1 - FEE)

    def _open_risk(self, lots, quotes):
        return sum((quantity * max(ZERO, quotes[symbol].bid - self._net_stop(stop))
                    for symbol, queue in lots.items() for quantity, stop in queue), ZERO)

    def _depth(self, quote, side):
        size = quote.ask_size if side == "BUY" else quote.bid_size
        used = sum((Decimal(fill["quantity"]) for fill in self.runtime.events
                    if fill["symbol"] == quote.symbol and fill["side"] == side
                    and fill["details"]["source_sequence"] == quote.source_sequence), ZERO)
        return max(ZERO, size - used)

    def control(self, action, *, expected_revision=None):
        with self.lock:
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
                raise PaperRejection("MARKET_DATA_HALT", "Fresh books for all three markets are required")
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
        order_id, symbol, side, quantity, stop, fingerprint = parse_order(payload)
        with self.lock:
            if order_id in self.runtime.order_ids:
                fill = next(event for event in self.runtime.events if event["order_id"] == order_id)
                if fill["details"]["fingerprint"] != fingerprint:
                    raise PaperRejection("IDEMPOTENCY_CONFLICT", "Order ID is already bound to different terms")
                return {"status": "ALREADY_COMMITTED", "fill": fill}
            now = self.clock()
            quotes, healthy, _ = self.feed.snapshot(now)
            account = self._refresh(now, quotes, healthy)
            if account is None:
                raise PaperRejection("MARKET_DATA_HALT", "Fresh books for all three markets are required")
            fill = self._fill(order_id, quotes[symbol], side, quantity, stop, fingerprint,
                              "manual", now, quotes, account)
            return {"status": "SIMULATED_FILL", "fill": fill}

    def _fill(self, order_id, quote, side, quantity, stop, fingerprint, origin, now, quotes, account):
        guard = self._guard()
        if not guard["enabled"] or self.runtime.ledger.halted:
            raise PaperRejection(guard["reason"], "Paper execution is halted")
        if quantity > self._depth(quote, side):
            raise PaperRejection("INSUFFICIENT_DEPTH", "Quantity exceeds remaining displayed top-of-book liquidity")
        if side == "SELL" and quantity > account["positions"].get(quote.symbol, ZERO):
            raise PaperRejection("INSUFFICIENT_POSITION", "Sell quantity exceeds the paper position")
        if side == "BUY" and (stop is None or stop >= quote.bid):
            raise PaperRejection("INVALID_STOP", "A protective stop below the current bid is required", 400)

        estimate = simulated_fill_estimate(quote, side=side, quantity=quantity, fee_rate=FEE,
                                           slippage_bps=SLIPPAGE * 10000)
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
        if (not all(healthy.values()) or not all(executable(item, now) for item in quotes.values())
                or any(current[symbol].source_sequence != item.source_sequence
                       for symbol, item in quotes.items())):
            raise PaperRejection("QUOTE_CHANGED", "The market snapshot changed. Retry with fresh quotes.")
        details = {
            "origin": origin, "fingerprint": fingerprint, "stop_price": str(stop) if stop is not None else None,
            "planned_stop_loss": str(loss), "source": quote.source, "source_time": quote.source_timestamp,
            "source_sequence": quote.source_sequence, "received_at": quote.observed_at.isoformat(),
            "filled_at": now.isoformat(),
        }
        try:
            self.runtime.execute(symbol=quote.symbol, side=side, quantity=quantity, reference_mid=quote.mid,
                                 executed_price=price, fee=fee, quote_timestamp=quote.exchange_at, now=now,
                                 marks=marks, proposed_loss=loss, aggregate_open_risk=aggregate,
                                 gross_notional=gross, peak_nav=peak, day_start_nav=day_start,
                                 operator_approved=True, order_id=order_id, details=details)
        except PermissionError as exc:
            self._set_control(False, "RISK_HALT")
            raise PaperRejection("RISK_HALT", str(exc)) from exc
        self._refresh(now, quotes, dict.fromkeys(PRODUCTS, True))
        return self.runtime.events[-1]

    def on_market_update(self):
        with self.lock:
            try:
                now = self.clock()
                quotes, healthy, _ = self.feed.snapshot(now)
                account = self._refresh(now, quotes, healthy)
                if account is None or not self._guard()["enabled"]:
                    return
                for symbol, lots in self._lots().items():
                    quote = quotes[symbol]
                    if lots and any(quote.bid <= stop for _, stop in lots):
                        quantity = min(account["positions"][symbol], self._depth(quote, "SELL"))
                        quantity = quantity.quantize(UNIT, rounding=ROUND_DOWN)
                        if quantity:
                            key = f"{symbol}:{quote.source_sequence}:{self.runtime.ledger.sequence}"
                            order_id = "stop_" + sha256(key.encode()).hexdigest()[:32]
                            self._fill(order_id, quote, "SELL", quantity, None, None,
                                       "protective_stop", now, quotes, account)
                            account = self._account({s: q.bid for s, q in quotes.items()})
            except PaperRejection:
                return
            except Exception:
                self.fail_closed()

    def state(self):
        with self.lock:
            now = self.clock()
            quotes, healthy, history = self.feed.snapshot(now)
            account = self._refresh(now, quotes, healthy)
            guard = self._guard()
            portfolio = {"cash": str(self.runtime.ledger.cash),
                         "positions": {s: str(q) for s, q in self.runtime.ledger.positions.items() if q},
                         "reconciled": account is not None}
            if account is not None:
                portfolio.update({key: str(account[key]) for key in ("nav", "fees", "realised", "unrealised")})
                portfolio["aggregate_stop_risk"] = str(self._open_risk(self._lots(), quotes))
            return {
                "mode": "SIMULATION_ONLY", "currency": "USD", "autonomous": False,
                "server_time": now.isoformat(),
                "market": {s: {"healthy": healthy[s], "source": q.source, "source_time": q.source_timestamp,
                               "age_seconds": round((now - q.exchange_at).total_seconds(), 2),
                               "bid": str(q.bid), "ask": str(q.ask), "bid_size": str(q.bid_size),
                               "ask_size": str(q.ask_size)} for s, q in quotes.items()},
                "history": history, "portfolio": portfolio,
                "risk": {"armed": bool(guard["enabled"]), "reason": guard["reason"],
                         "can_arm": self._can_arm(guard, account), "revision": guard["revision"],
                         "day_start_nav": guard["day_start"], "peak_nav": guard["peak"],
                         "data_healthy": all(healthy.values())},
                "fills": list(reversed(self.runtime.events[-30:])),
            }
