"""Fail-closed research evidence stress screen; no promotion authority."""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class StressResult:
    verdict: str
    net_returns: tuple
    tested_costs_bps: tuple
    reason: str

def stress_costs(gross_returns, *, costs_bps=(20, 40, 60, 80), minimum_trades=40):
    """One gross per-trade simple return; costs are round-trip basis points.

    This is a preliminary sensitivity screen, not a backtest or proof of edge.
    """
    gross = tuple(float(x) for x in gross_returns)
    costs = tuple(float(x) for x in costs_bps)
    if minimum_trades < 1 or not costs or any(not isfinite(x) or x < 0 for x in costs):
        raise ValueError("invalid cost assumptions")
    if any(not isfinite(x) or x <= -1 for x in gross):
        raise ValueError("invalid gross returns")
    if len(gross) < minimum_trades:
        return StressResult("REJECT", (), costs, "insufficient trades")
    net = tuple(sum(x - c / 10000.0 for x in gross) for c in costs)
    if any(x <= 0 for x in net):
        return StressResult("REJECT", net, costs, "fails at least one cost stress")
    return StressResult("REVIEW_ONLY", net, costs, "positive cost screen; independent evidence gates still required")
