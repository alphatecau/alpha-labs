"""Offline fail-closed risk eligibility for research proposals only.

NOT linked to a broker. A PASS does not authorise paper or live execution.
All quantities are in a single explicit quote currency; no FX conversion.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite decimal")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{label} must be a finite decimal")
    return number


@dataclass(frozen=True)
class RiskPolicy:
    max_new_position_fraction: Decimal = Decimal("0.20")
    max_total_exposure_fraction: Decimal = Decimal("0.30")
    max_daily_loss_fraction: Decimal = Decimal("0.02")
    max_drawdown_fraction: Decimal = Decimal("0.05")
    max_quote_age_seconds: int = 180

    def __post_init__(self):
        for name in (
            "max_new_position_fraction", "max_total_exposure_fraction",
            "max_daily_loss_fraction", "max_drawdown_fraction",
        ):
            v = _decimal(getattr(self, name), name)
            if not Decimal("0") < v <= Decimal("1"):
                raise ValueError(f"Invalid {name}")
            object.__setattr__(self, name, v)
        if isinstance(self.max_quote_age_seconds, bool) or not isinstance(self.max_quote_age_seconds, int) or self.max_quote_age_seconds < 1:
            raise ValueError("Invalid quote age limit")


@dataclass(frozen=True)
class ResearchProposal:
    equity: Decimal
    open_exposure: Decimal
    proposed_notional: Decimal
    realised_daily_pnl: Decimal
    drawdown_fraction: Decimal
    quote_age_seconds: int
    data_integrity_ok: bool
    kill_switch_active: bool
    side: str = "LONG"


@dataclass(frozen=True)
class RiskAssessment:
    status: str
    reasons: tuple[str, ...]
    passes_research_checks: bool
    execution_authorised: bool = False


def assess_proposal(proposal: ResearchProposal, policy: RiskPolicy | None = None) -> RiskAssessment:
    """A conservative, deterministic proposal check; never emits an order or permission."""
    if not isinstance(proposal, ResearchProposal):
        raise TypeError("ResearchProposal required")
    policy = policy if policy is not None else RiskPolicy()
    if not isinstance(policy, RiskPolicy):
        raise TypeError("RiskPolicy required")
    nums = {name: _decimal(getattr(proposal, name), name) for name in (
        "equity", "open_exposure", "proposed_notional", "realised_daily_pnl", "drawdown_fraction",
    )}
    reasons: list[str] = []
    if nums["equity"] <= 0:
        reasons.append("INVALID_EQUITY")
    if nums["open_exposure"] < 0 or nums["proposed_notional"] <= 0:
        reasons.append("INVALID_NOTIONAL")
    if not Decimal("0") <= nums["drawdown_fraction"] <= Decimal("1"):
        reasons.append("INVALID_DRAWDOWN")
    if (isinstance(proposal.quote_age_seconds, bool)
            or not isinstance(proposal.quote_age_seconds, int)
            or proposal.quote_age_seconds < 0):
        reasons.append("INVALID_QUOTE_AGE")
    if type(proposal.data_integrity_ok) is not bool or not proposal.data_integrity_ok:
        reasons.append("UNVERIFIED_DATA")
    if type(proposal.kill_switch_active) is not bool or proposal.kill_switch_active:
        reasons.append("KILL_SWITCH_ACTIVE_OR_UNKNOWN")
    if proposal.side != "LONG":
        reasons.append("UNSUPPORTED_SIDE")
    if isinstance(proposal.quote_age_seconds, int) and proposal.quote_age_seconds > policy.max_quote_age_seconds:
        reasons.append("STALE_QUOTE")
    # Only calculate limits on meaningful, nonnegative inputs.
    if nums["equity"] > 0:
        equity = nums["equity"]
        if nums["proposed_notional"] > equity * policy.max_new_position_fraction:
            reasons.append("NEW_POSITION_LIMIT")
        if nums["open_exposure"] + nums["proposed_notional"] > equity * policy.max_total_exposure_fraction:
            reasons.append("TOTAL_EXPOSURE_LIMIT")
        if nums["realised_daily_pnl"] <= -equity * policy.max_daily_loss_fraction:
            reasons.append("DAILY_LOSS_LIMIT")
    if nums["drawdown_fraction"] >= policy.max_drawdown_fraction:
        reasons.append("DRAWDOWN_LIMIT")
    ok = not reasons
    return RiskAssessment(
        status="RESEARCH_ONLY_PASS" if ok else "REJECTED",
        reasons=tuple(reasons),
        passes_research_checks=ok,
        execution_authorised=False,
    )
