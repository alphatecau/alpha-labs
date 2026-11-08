"""Fail-closed independent simulated-only portfolio risk policy."""
from dataclasses import dataclass
from decimal import Decimal
from alpha_lab.research.paper_simulator import number

@dataclass(frozen=True)
class PaperRiskLimits:
    max_position_risk_pct: Decimal = Decimal("0.0025")
    max_aggregate_risk_pct: Decimal = Decimal("0.01")
    daily_loss_halt_pct: Decimal = Decimal("0.02")
    drawdown_halt_pct: Decimal = Decimal("0.05")
    max_notional_multiple: Decimal = Decimal("1")

def authorise_simulated_order(*, nav, initial_nav, peak_nav, day_start_nav,
                             proposed_loss, aggregate_open_risk, gross_notional,
                             proposed_notional, data_fresh, ledger_reconciled,
                             operator_enabled, limits=PaperRiskLimits()):
    """Pure independent decision; does not submit, sign or execute any order."""
    reasons = []
    try:
        n, initial, peak, day, loss, aggregate, gross, proposed = map(
            number, (nav, initial_nav, peak_nav, day_start_nav, proposed_loss,
                     aggregate_open_risk, gross_notional, proposed_notional))
        if min(n, initial, peak, day) <= 0 or min(loss, aggregate, gross, proposed) < 0:
            reasons.append("invalid risk inputs")
        else:
            if loss > n * limits.max_position_risk_pct:
                reasons.append("position risk exceeded")
            if aggregate + loss > n * limits.max_aggregate_risk_pct:
                reasons.append("aggregate risk exceeded")
            if day - n >= day * limits.daily_loss_halt_pct:
                reasons.append("daily loss HALT")
            if peak - n >= peak * limits.drawdown_halt_pct:
                reasons.append("drawdown HALT")
            if gross + proposed > n * limits.max_notional_multiple:
                reasons.append("gross notional exceeded")
    except (ValueError, TypeError, KeyError):
        reasons.append("invalid risk inputs")
    if data_fresh is not True:
        reasons.append("stale or unverified market data")
    if ledger_reconciled is not True:
        reasons.append("unreconciled ledger")
    if operator_enabled is not True:
        reasons.append("operator HALT")
    return {"approved": not reasons, "mode": "SIMULATION_ONLY",
            "reasons": reasons, "live_execution_authorised": False}
