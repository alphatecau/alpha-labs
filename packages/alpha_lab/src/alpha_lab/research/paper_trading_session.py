"""Authority-enforced offline paper-trading session.

This facade is the supported paper-first entry point. It never calls a broker.
The underlying legacy simulator is retained for backward-compatible research tests.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from alpha_lab.research.paper_first_authority import (
    Mode, TradingAuthority, authorise_simulation, live_copy_readiness,
)
from alpha_lab.research.paper_simulator import PaperLedger


@dataclass
class PaperTradingSession:
    authority: TradingAuthority = field(default_factory=TradingAuthority)
    ledger: PaperLedger = field(default_factory=PaperLedger)
    _guard: object = field(default_factory=object, init=False, repr=False)

    def __post_init__(self):
        if not isinstance(self.authority, TradingAuthority):
            raise ValueError("Invalid authority")
        if not isinstance(self.ledger, PaperLedger):
            raise ValueError("Invalid paper ledger")
        if self.ledger._session_guard is not None:
            raise ValueError("Ledger already belongs to a session")
        self.ledger._session_guard = self._guard
        self.ledger.halt()

    def set_authority(self, authority: TradingAuthority):
        """Changing permissions always halts and requires new paper approval."""
        self.ledger.halt()
        if not isinstance(authority, TradingAuthority):
            raise ValueError("Invalid authority")
        self.authority = authority

    def start_paper(self, *, operator_approved=False):
        decision = authorise_simulation(self.authority)
        if decision["decision"] != "PAPER_ONLY":
            self.ledger.halt()
            raise PermissionError("Paper session is halted")
        self.ledger._session_enable(self._guard, operator_approved=operator_approved)
        return {"mode": Mode.PAPER.value, "execution": "SIMULATED", "real_money": False}

    def simulate_fill(self, **kwargs):
        decision = authorise_simulation(self.authority)
        if decision["decision"] != "PAPER_ONLY":
            self.ledger.halt()
            raise PermissionError("Authority denied simulated fill")
        if "simulated_only" in kwargs:
            self.ledger.halt()
            raise PermissionError("Caller cannot override simulated-only mode")
        return self.ledger._session_fill(self._guard, **kwargs, simulated_only=True)

    def halt(self):
        self.ledger.halt()

    def status(self, marks=None):
        try:
            decision = authorise_simulation(self.authority)
        except PermissionError:
            decision = {"decision": "HALT"}
        if decision["decision"] != "PAPER_ONLY":
            self.ledger.halt()
        result = {"mode": Mode.PAPER.value, "real_money": False,
                  "paper_halted": self.ledger.halted,
                  "live_copy": live_copy_readiness(self.authority)}
        if marks is not None:
            result["paper"] = self.ledger.snapshot(marks)
        return result
