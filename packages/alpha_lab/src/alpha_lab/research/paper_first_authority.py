"""Paper-first product authority. No broker integration or live execution.

An opt-in preference is not permission to submit a real order. This module
deliberately contains no live broker client, credentials or execution method.
"""
from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    PAPER = "PAPER"
    LIVE_COPY = "LIVE_COPY"


@dataclass(frozen=True)
class TradingAuthority:
    requested_mode: Mode = Mode.PAPER
    user_opt_in: bool = False
    regulatory_approved: bool = False
    strategy_independently_validated: bool = False
    broker_integration_approved: bool = False
    independent_risk_gate_approved: bool = False
    deployment_approved: bool = False
    emergency_halt: bool = True


def authorise_simulation(authority: TradingAuthority) -> dict:
    """Only research/paper mode can proceed. Live is fail-closed."""
    if not isinstance(authority, TradingAuthority):
        raise ValueError("Invalid authority")
    if authority.requested_mode != Mode.PAPER:
        raise PermissionError("Live copy execution is not implemented or authorised")
    if authority.emergency_halt:
        return {"decision": "HALT", "execution": "NONE", "real_money": False}
    return {"decision": "PAPER_ONLY", "execution": "SIMULATED", "real_money": False}


def live_copy_readiness(authority: TradingAuthority) -> dict:
    """Read-only assessment; never submits an order."""
    if not isinstance(authority, TradingAuthority):
        raise ValueError("Invalid authority")
    checks = {
        "explicit_user_opt_in": authority.user_opt_in,
        "regulatory_approval": authority.regulatory_approved,
        "independent_strategy_validation": authority.strategy_independently_validated,
        "broker_integration_approval": authority.broker_integration_approved,
        "independent_risk_gate": authority.independent_risk_gate_approved,
        "deployment_approval": authority.deployment_approved,
        "emergency_halt_cleared": not authority.emergency_halt,
    }
    return {"target_mode": Mode.LIVE_COPY.value, "checks": checks,
            "implemented": False, "can_execute": False,
            "status": "DISABLED_NOT_IMPLEMENTED"}
