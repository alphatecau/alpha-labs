"""Research-only guarded runtime facade; no HTTP authentication or broker access.

The caller must be trusted Python code. Never expose raw PaperRuntime to web users.
"""
from alpha_lab.research.paper_first_authority import TradingAuthority, authorise_simulation
from alpha_lab.research.paper_runtime import PaperRuntime


class GuardedPaperRuntime:
    def __init__(self, path, *, authority=None, starting_cash="10000"):
        self.authority = authority if authority is not None else TradingAuthority()
        if not isinstance(self.authority, TradingAuthority):
            raise ValueError("Invalid trading authority")
        self._runtime = PaperRuntime(path, starting_cash=starting_cash)

    def set_authority(self, authority):
        self._runtime.ledger.halt()
        if not isinstance(authority, TradingAuthority):
            raise ValueError("Invalid trading authority")
        self.authority = authority

    def _require_paper(self):
        try:
            decision = authorise_simulation(self.authority)
        except (PermissionError, ValueError):
            self._runtime.ledger.halt()
            raise PermissionError("HALT: paper authority denied")
        if decision["decision"] != "PAPER_ONLY":
            self._runtime.ledger.halt()
            raise PermissionError("HALT: paper authority denied")

    def enable(self, *, operator_approved=False):
        self._require_paper()
        return self._runtime.enable(operator_approved=operator_approved)

    def execute(self, **kwargs):
        self._require_paper()
        if kwargs.get("operator_approved") is not True:
            self._runtime.ledger.halt()
            raise PermissionError("HALT: explicit operator approval required")
        return self._runtime.execute(**kwargs)

    def status(self):
        return {"mode": "PAPER", "halted": self._runtime.ledger.halted,
                "recovery_verified": self._runtime.recovery_verified,
                "live_copy_enabled": False, "broker_connected": False}

    def close(self):
        self._runtime.close()
