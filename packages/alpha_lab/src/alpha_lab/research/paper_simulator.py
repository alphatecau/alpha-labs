"""Offline-only simulated fills. No broker/network interfaces or autonomous scheduler.

Research scaffold, not a production paper trading service.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json

def number(value):
    try:
        x = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid numeric input") from exc
    if not x.is_finite():
        raise ValueError("non-finite numeric input")
    return x

@dataclass
class PaperLedger:
    starting_cash: Decimal = Decimal("10000")
    cash: Decimal = field(init=False)
    positions: dict = field(default_factory=dict)
    fills: list = field(default_factory=list)
    halted: bool = True
    sequence: int = 0
    audit_hash: str = "0" * 64

    def __post_init__(self):
        self.starting_cash = number(self.starting_cash)
        if self.starting_cash <= 0:
            raise ValueError("initial cash must be positive")
        self.cash = self.starting_cash

    def halt(self):
        self.halted = True

    def enable_simulation(self, *, operator_approved=False):
        if operator_approved is not True:
            raise PermissionError("explicit simulated-only operator approval required")
        self.halted = False

    def fill(self, *, symbol, side, quantity, reference_mid, executed_price,
             fee, observed_quote=True, simulated_only=True):
        if self.halted:
            raise PermissionError("HALT: simulated execution denied")
        if simulated_only is not True or observed_quote is not True:
            self.halt()
            raise PermissionError("unsafe execution context: HALT")
        if not isinstance(symbol, str) or not symbol or len(symbol) > 32:
            raise ValueError("invalid symbol")
        if side not in ("BUY", "SELL"):
            raise ValueError("unsupported side")
        q, mid, px, f = map(number, (quantity, reference_mid, executed_price, fee))
        if q <= 0 or mid <= 0 or px <= 0 or f < 0:
            raise ValueError("invalid fill values")
        current = self.positions.get(symbol, Decimal(0))
        if side == "SELL" and q > current:
            raise ValueError("naked short denied")
        delta = -(q * px + f) if side == "BUY" else q * px - f
        if self.cash + delta < 0:
            raise ValueError("negative cash denied")
        # No external execution side effects. Commit only after all checks.
        self.cash += delta
        self.positions[symbol] = current + (q if side == "BUY" else -q)
        self.sequence += 1
        shortfall = q * (px - mid) * (1 if side == "BUY" else -1)
        record = {"seq": self.sequence, "symbol": symbol, "side": side,
                  "quantity": str(q), "price": str(px), "reference_mid": str(mid),
                  "fee": str(f), "cash_delta": str(delta),
                  "shortfall_vs_mid": str(shortfall), "simulated": True,
                  "previous_hash": self.audit_hash}
        self.audit_hash = sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
        record["audit_hash"] = self.audit_hash
        self.fills.append(record)
        return dict(record)

    def nav(self, marks):
        total = self.cash
        for symbol, quantity in self.positions.items():
            if quantity:
                if symbol not in marks:
                    self.halt()
                    raise ValueError("missing closing mark: HALT")
                mark = number(marks[symbol])
                if mark <= 0:
                    self.halt()
                    raise ValueError("invalid closing mark: HALT")
                total += quantity * mark
        return total

    def snapshot(self, marks):
        return {"mode": "SIMULATION_ONLY", "halted": self.halted,
                "cash": str(self.cash),
                "positions": {k: str(v) for k, v in self.positions.items()},
                "nav": str(self.nav(marks)), "fills": len(self.fills),
                "audit_hash": self.audit_hash}
