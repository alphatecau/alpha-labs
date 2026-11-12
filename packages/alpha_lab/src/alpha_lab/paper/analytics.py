"""Descriptive simulation analytics; sparse metrics remain explicitly unavailable."""
from decimal import Decimal as D


def describe(snapshot, events):
    account = snapshot["account"]
    equity, initial = D(account["last_equity"]), D(account["initial_cash"])
    fills = [e["payload"] for e in events if e["kind"] == "FILL"]
    pnl = equity-initial
    return dict(schema="alpha-labs.analytics.v1", currency=account["currency"],
                simulated=True, net_pnl=str(pnl), net_return=str(pnl/initial),
                realised_pnl=account["realised_pnl"],
                unrealised_pnl=str(sum((D(p["unrealised_pnl"]) for p in snapshot["positions"]), D(0))),
                modelled_fees=account["fees"], fill_count=len(fills),
                current_drawdown=str(1-equity/D(account["peak_equity"])),
                historical_max_drawdown=None, sharpe=None, profit_factor=None,
                expectancy=None, benchmark_excess=None,
                unavailable_reason="UNVERIFIED: no independently evaluated return series or trade sample",
                operating_expenses_included=False, execution_costs_calibrated=False)
