"""Offline research-only settlement, independent ledger reconciliation and PostgreSQL DDL.

No database connection, external exchange calendar or trading is performed here.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from alpha_lab.research.point_in_time_guards import finite_decimal, utc_instant

POSTGRES_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS research_run_registry (
    owner_id TEXT NOT NULL CHECK (length(btrim(owner_id)) > 0),
    run_id TEXT NOT NULL CHECK (length(btrim(run_id)) > 0),
    evidence_sha256 TEXT NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (owner_id, run_id)
);
"""

POSTGRES_INSERT_RUN_SQL = """
INSERT INTO research_run_registry (owner_id, run_id, evidence_sha256)
VALUES (%s, %s, %s)
RETURNING owner_id, run_id
"""

def register_postgres_run(cursor, owner_id, run_id, evidence_sha256):
    """Caller owns transaction. UNIQUE violation must propagate; never use ON CONFLICT DO NOTHING."""
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise ValueError("owner id required")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run id required")
    import re
    if not isinstance(evidence_sha256, str) or not re.fullmatch("[0-9a-f]{64}", evidence_sha256):
        raise ValueError("lowercase SHA256 required")
    cursor.execute(POSTGRES_INSERT_RUN_SQL, (owner_id, run_id, evidence_sha256))
    return cursor.fetchone()

@dataclass(frozen=True)
class Session:
    opens: datetime
    closes: datetime

def validate_sessions(sessions):
    if not isinstance(sessions, (tuple, list)) or not sessions:
        raise ValueError("explicit exchange sessions required")
    previous = None
    for session in sessions:
        opened, closed = utc_instant(session.opens), utc_instant(session.closes)
        if opened >= closed or (previous is not None and opened < previous):
            raise ValueError("overlapping, unordered or invalid sessions")
        previous = closed
    return tuple(sessions)

def next_eligible_open(decision_at, sessions):
    """Next strictly later session opening, never an invented holiday/weekend fill."""
    decision = utc_instant(decision_at)
    for session in validate_sessions(sessions):
        if utc_instant(session.opens) > decision:
            return utc_instant(session.opens)
    raise ValueError("no future verified market session available")

def require_settlement_at_open(decision_at, settlement_at, sessions):
    expected = next_eligible_open(decision_at, sessions)
    if utc_instant(settlement_at) != expected:
        raise ValueError("settlement must equal next verified session opening")
    return expected

def reconcile_long_only_orders(starting_cash, orders, last_price, costs, expected_nav):
    """Independently replay recorded BUY/SELL cash flows and liquidation-value mark."""
    cash = finite_decimal(starting_cash, nonnegative=True)
    quantity = Decimal("0")
    realised = Decimal("0")
    entry_cost = Decimal("0")
    fees = Decimal("0")
    for order in orders:
        if not isinstance(order, dict):
            raise ValueError("malformed order")
        kind = order.get("kind")
        q = finite_decimal(order.get("quantity"), nonnegative=True)
        fee = finite_decimal(order.get("fee"), nonnegative=True)
        if q <= 0:
            raise ValueError("zero-quantity order")
        if kind == "BUY":
            outlay = finite_decimal(order.get("quote_outlay"), nonnegative=True)
            if quantity:
                raise ValueError("multiple open long positions")
            cash -= outlay
            quantity = q
            entry_cost = outlay
        elif kind == "SELL":
            proceeds = finite_decimal(order.get("quote_received"), nonnegative=True)
            if q != quantity or quantity == 0:
                raise ValueError("sell quantity does not match position")
            cash += proceeds
            realised += proceeds - entry_cost
            quantity = Decimal("0")
            entry_cost = Decimal("0")
        else:
            raise ValueError("unknown order kind")
        fees += fee
        if cash < Decimal("-1e-12"):
            raise ValueError("negative cash after order")
    mark = finite_decimal(last_price, nonnegative=True)
    nav = cash + costs.sell_proceeds(quantity, mark)
    if nav != finite_decimal(expected_nav):
        raise ValueError("NAV reconciliation mismatch")
    return {"cash": cash, "quantity": quantity, "realised_pnl": realised,
            "unrealised_liquidation_pnl": costs.sell_proceeds(quantity, mark) - entry_cost,
            "total_modelled_fees": fees, "nav": nav}


def require_venue_bar_open(bar_time, sessions, *, venue):
    """Reject any bar opening outside explicit exchange sessions; fail closed for equities."""
    if venue != "equity":
        raise ValueError("unsupported venue for session-based execution")
    instant = utc_instant(bar_time)
    if not any(utc_instant(s.opens) <= instant < utc_instant(s.closes)
               for s in validate_sessions(sessions)):
        raise ValueError("execution outside verified exchange session")
    return instant


def reconstruct_replay_economics(bars, orders, starting_cash, costs, expected_nav, *, last_close):
    """Independently reconstruct recorded next-open long-only execution economics."""
    from decimal import Decimal
    bar_by_time = {utc_instant(b.time): b for b in bars}
    if len(bar_by_time) != len(bars):
        raise ValueError("duplicate bar times")
    cash = finite_decimal(starting_cash, nonnegative=True)
    qty = Decimal("0")
    entry = Decimal("0")
    realised = Decimal("0")
    fees = Decimal("0")
    last_order_time = None
    for order in orders:
        when = utc_instant(datetime.fromisoformat(order["time"]))
        if when not in bar_by_time or (last_order_time is not None and when <= last_order_time):
            raise ValueError("unknown or unordered execution bar")
        last_order_time = when
        open_price = finite_decimal(bar_by_time[when].open, nonnegative=True)
        quantity = finite_decimal(order.get("quantity"), nonnegative=True)
        if quantity <= 0 or open_price <= 0:
            raise ValueError("invalid quantity or source price")
        kind = order.get("kind")
        if kind == "BUY":
            if qty:
                raise ValueError("duplicate entry")
            execution_price = costs.buy_price(open_price)
            fee = quantity * execution_price * costs.fee_bps / Decimal("10000")
            outlay = quantity * execution_price + fee
            if outlay > cash:
                raise ValueError("insufficient cash")
            if finite_decimal(order.get("quote_outlay")) != outlay:
                raise ValueError("buy outlay mismatch")
            cash -= outlay
            qty = quantity
            entry = outlay
        elif kind == "SELL":
            if quantity != qty:
                raise ValueError("sell quantity mismatch")
            execution_price = costs.sell_price(open_price)
            fee = quantity * execution_price * costs.fee_bps / Decimal("10000")
            proceeds = quantity * execution_price - fee
            if finite_decimal(order.get("quote_received")) != proceeds:
                raise ValueError("sell proceeds mismatch")
            cash += proceeds
            realised += proceeds - entry
            qty = Decimal("0")
            entry = Decimal("0")
        else:
            raise ValueError("invalid order side")
        if finite_decimal(order.get("price")) != execution_price:
            raise ValueError("execution price mismatch")
        if finite_decimal(order.get("fee")) != fee:
            raise ValueError("execution fee mismatch")
        fees += fee
    close = finite_decimal(last_close, nonnegative=True)
    nav = cash + costs.sell_proceeds(qty, close)
    if nav != finite_decimal(expected_nav):
        raise ValueError("reconstructed NAV mismatch")
    return {"cash":cash,"quantity":qty,"realised_pnl":realised,
            "unrealised_liquidation_pnl":costs.sell_proceeds(qty,close)-entry,
            "fees":fees,"nav":nav}
