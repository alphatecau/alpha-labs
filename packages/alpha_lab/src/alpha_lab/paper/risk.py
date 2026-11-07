"""Deterministic simulation risk authority. No agent-owned policy inputs."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .contracts import Mode, Outcome, Proposal, Quote, number, utc

D = Decimal
TERMINAL = {"FILLED", "CANCELLED", "REJECTED"}


@dataclass(frozen=True)
class Limits:
    position_loss: D = D("0.0025")
    aggregate_stop_risk: D = D("0.01")
    daily_loss: D = D("0.02")
    drawdown: D = D("0.05")
    notional: D = D("1")
    concentration: D = D("0.20")
    total_exposure: D = D("0.30")
    weekly_loss: D = D("0.04")
    depth_fraction: D = D("0.10")
    price_deviation: D = D("0.01")
    max_orders_per_minute: int = 10

    def __post_init__(self):
        ceilings = dict(position_loss="0.0025", aggregate_stop_risk="0.01",
                        daily_loss="0.02", drawdown="0.05", notional="1",
                        concentration="0.20", total_exposure="0.30", weekly_loss="0.04",
                        depth_fraction="0.10", price_deviation="0.01")
        for name, ceiling in ceilings.items():
            val = number(getattr(self, name), positive=True)
            if val > D(ceiling):
                raise ValueError(f"{name} exceeds platform ceiling")
            object.__setattr__(self, name, val)
        if type(self.max_orders_per_minute) is not int or not 1 <= self.max_orders_per_minute <= 10:
            raise ValueError("invalid frequency limit")


@dataclass(frozen=True)
class CostModel:
    """Explicit engineering assumptions, never calibrated venue costs."""
    fee_bps: D = D("10")
    slippage_bps: D = D("5")
    gap_buffer: D = D("0.01")

    def __post_init__(self):
        for name in ("fee_bps", "slippage_bps", "gap_buffer"):
            val = number(getattr(self, name), minimum="0")
            if val >= (D("1") if name == "gap_buffer" else D("1000")):
                raise ValueError("unsupported simulation cost assumption")
            object.__setattr__(self, name, val)

    def price(self, quote: Quote, side: str):
        if side == "BUY":
            return quote.ask * (1+self.slippage_bps/10000)
        if side == "SELL":
            return quote.bid * (1-self.slippage_bps/10000)
        raise ValueError("unsupported side")

    def fee(self, quantity, price):
        return quantity*price*self.fee_bps/10000

    def planned_loss(self, quantity, price, stop):
        return quantity*(price-stop + stop*self.gap_buffer) + self.fee(quantity, price+stop)


class RiskAuthoriser:
    def __init__(self, costs: CostModel | None = None):
        self.costs = costs or CostModel()

    def evaluate_exit(self, quote, account, position, now, *, broker_connected):
        """Independent reduce-only check; HALT never requires opening exposure."""
        quote.check(now)
        limits = Limits(**account["limits"])
        reasons = []
        if account["mode"] != Mode.SIMULATION or broker_connected is not True:
            reasons.append("EXIT_MODE_OR_CONNECTIVITY_BLOCKED")
        if (quote.instrument != position["instrument"] or not quote.synthetic
                or quote.venue != "synthetic" or quote.instrument != "TEST/AUD"
                or quote.currency != account["currency"] or quote.asset_class != "crypto_spot"):
            reasons.append("EXIT_FIXTURE_SCOPE_MISMATCH")
        if D(position["quantity"]) > quote.bid_size*limits.depth_fraction:
            reasons.append("EXIT_LIQUIDITY_BLOCKED")
        if utc(now) < utc(account["last_time"]):
            reasons.append("CLOCK_REGRESSION")
        return tuple(reasons)

    def evaluate(self, proposal: Proposal, quote: Quote, account: dict,
                 positions: list[dict], orders: list[dict], now: str,
                 *, broker_connected: bool) -> tuple[tuple[str, ...], D, D]:
        limits = Limits(**account["limits"])
        reasons = []
        if account["mode"] != Mode.SIMULATION:
            reasons.append("MODE_NOT_SIMULATION")
        if account["halted"]:
            reasons.append("PERSISTENT_HALT")
        if not account["enabled"]:
            reasons.append("SIMULATION_SUSPENDED")
        if broker_connected is not True:
            reasons.append("BROKER_DISCONNECTED")
        if quote.instrument != proposal.instrument or quote.currency != account["currency"]:
            reasons.append("INSTRUMENT_OR_CURRENCY_MISMATCH")
        quote.check(now)
        if quote.asset_class != "crypto_spot":
            reasons.append("ASSET_EXECUTION_UNSUPPORTED")
        if not quote.synthetic:
            reasons.append("REAL_STRATEGY_EXECUTION_UNVERIFIED")
        if utc(now) < utc(account["last_time"]):
            reasons.append("CLOCK_REGRESSION")
        equity, cash = D(account["last_equity"]), D(account["cash"])
        if equity <= 0:
            return tuple(reasons + ["INSOLVENT"]), D(0), D(0)
        if equity <= D(account["day_start"])*(1-limits.daily_loss):
            reasons.append("DAILY_LOSS_SUSPENSION")
        if equity <= D(account["week_start"])*(1-limits.weekly_loss):
            reasons.append("WEEKLY_LOSS_SUSPENSION")
        if equity <= D(account["peak_equity"])*(1-limits.drawdown):
            reasons.append("DRAWDOWN_SUSPENSION")
        pending = [o for o in orders if o["status"] not in TERMINAL]
        if pending:
            # One outstanding order per account prevents unmodelled reservation races.
            reasons.append("PENDING_ORDER_REQUIRES_RECONCILIATION")
        if any(D(p["quantity"]) > 0 and p["instrument"] == proposal.instrument for p in positions):
            reasons.append("EXISTING_POSITION_UNSUPPORTED")
        recent = sum(0 <= (utc(now)-utc(o["created_at"])).total_seconds() < 60 for o in orders)
        if recent >= limits.max_orders_per_minute:
            reasons.append("ORDER_FREQUENCY_LIMIT")
        if proposal.direction != Outcome.LONG:
            reasons.append("SIDE_UNSUPPORTED")
        price = self.costs.price(quote, "BUY")
        if proposal.stop_price >= price:
            reasons.append("INVALID_LONG_STOP")
        loss = self.costs.planned_loss(proposal.quantity, price, proposal.stop_price)
        fee = self.costs.fee(proposal.quantity, price)
        notional = proposal.quantity*price
        if proposal.quantity > quote.ask_size*limits.depth_fraction:
            reasons.append("LIQUIDITY_LIMIT")
        if (price-quote.midpoint)/quote.midpoint > limits.price_deviation:
            reasons.append("PRICE_DEVIATION_LIMIT")
        if proposal.limit_price is not None and price > proposal.limit_price:
            reasons.append("LIMIT_NOT_MARKETABLE")
        exposure = sum((D(p["quantity"])*D(p["mark"]) for p in positions), D(0))
        stop_risk = sum((D(p["planned_loss"]) for p in positions), D(0))
        if loss > equity*limits.position_loss:
            reasons.append("POSITION_LOSS_LIMIT")
        if stop_risk+loss > equity*limits.aggregate_stop_risk:
            reasons.append("AGGREGATE_STOP_RISK_LIMIT")
        if notional > equity*limits.concentration:
            reasons.append("CONCENTRATION_LIMIT")
        if exposure+notional > equity*min(limits.notional, limits.total_exposure):
            reasons.append("EXPOSURE_LIMIT")
        if notional+fee > cash:
            reasons.append("INSUFFICIENT_BUYING_POWER")
        return tuple(reasons), fee, loss
