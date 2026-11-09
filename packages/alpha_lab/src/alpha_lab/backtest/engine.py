"""Offline long-only next-open replay. Not an executable quote model or live trading engine."""
from dataclasses import dataclass, asdict
from decimal import Decimal
from .costs import CostModel
from alpha_lab.data.csv_import import Bar
from alpha_lab.research.point_in_time_guards import finite_decimal, require_final_candle, utc_instant

@dataclass(frozen=True)
class RunResult:
    starting_balance: str
    final_liquidatable_value: str
    pnl: str
    return_pct: float
    max_drawdown_pct: float
    executed_orders: int
    closed_trades: int
    open_position: bool
    total_modelled_fees: str
    estimated_unexecuted_exit_fee_in_nav: str
    orders: list[dict]

def _render(cash, qty, price, costs):
    # Mark to market at conservative assumed exit value; no real order occurs.
    return cash+costs.sell_proceeds(qty,price)

def replay(bars: tuple[Bar,...], signals: list[bool], start: int, end: int, *,
           starting_balance=Decimal('10000'), max_allocation=Decimal('0.20'),
           costs=CostModel(), passive=False) -> RunResult:
    starting_balance = finite_decimal(starting_balance, nonnegative=True)
    max_allocation = finite_decimal(max_allocation, nonnegative=True)
    if starting_balance == 0:
        raise ValueError('starting balance must be positive')
    # Validate all candles and signal timestamps before accepting any simulated order.
    for j, bar in enumerate(bars):
        utc_instant(bar.time)
        for value in (bar.open, bar.high, bar.low, bar.close, bar.volume):
            finite_decimal(value, nonnegative=True)
        if j and bar.time <= bars[j-1].time:
            raise ValueError('unordered or duplicate candle timestamps')
    intervals = [(bars[j].time - bars[j-1].time).total_seconds() for j in range(1, len(bars))]
    if not intervals or min(intervals) < 60 or min(intervals) % 60:
        raise ValueError('cannot establish positive whole-minute candle interval')
    inferred_interval_minutes = int(min(intervals) // 60)
    if not (1<=start<end<=len(bars)) or len(signals)!=len(bars): raise ValueError('invalid range or signals')
    if not (Decimal('0')<max_allocation<=Decimal('1')) or starting_balance<=0:
        raise ValueError('invalid capital controls')
    cash=Decimal(starting_balance);qty=Decimal(0);peak=Decimal(starting_balance);dd=Decimal(0)
    orders=[];total_fees=Decimal(0);completed=0;open_entry=None
    for i in range(start,end):
        # A decision based on the previous close is eligible at the next open
        # only if that previous interval has fully closed.
        if i > 0:
            # Infer the shortest observed bar interval; longer gaps may be holidays.
            # Explicit exchange-calendar settlement remains a separate requirement.
            require_final_candle(bars[i-1].time, inferred_interval_minutes, bars[i].time)
        price=bars[i].open
        # Close-bar signal is available only at the following candle open.
        should_hold = (i==start or qty>0) if passive else signals[i-1]
        if should_hold and qty==0:
            quote_budget=min(cash, Decimal(starting_balance)*max_allocation)
            q=costs.buy_quantity(quote_budget,price)
            cost=costs.buy_outlay(q,price)
            assert q>=0 and cost<=cash+Decimal('1e-15')
            fee=q*costs.buy_price(price)*costs.fee_bps/10000
            total_fees+=fee;cash-=cost;qty=q;open_entry=cost
            orders.append({'kind':'BUY','time':bars[i].time.isoformat(),'price':str(costs.buy_price(price)),
                           'quantity':str(q),'quote_outlay':str(cost),'fee':str(fee),'source':'modelled_next_open'})
        elif not should_hold and qty>0:
            proceeds=costs.sell_proceeds(qty,price)
            fee=qty*costs.sell_price(price)*costs.fee_bps/10000
            total_fees+=fee;cash+=proceeds
            orders.append({'kind':'SELL','time':bars[i].time.isoformat(),'price':str(costs.sell_price(price)),
                           'quantity':str(qty),'quote_received':str(proceeds),'fee':str(fee),
                           'modelled_trade_pnl':str(proceeds-open_entry),'source':'modelled_next_open'})
            qty=Decimal(0);completed+=1;open_entry=None
        nav=_render(cash,qty,bars[i].close,costs)
        if nav>peak: peak=nav
        dd=max(dd,(peak-nav)/peak)
    ending=_render(cash,qty,bars[end-1].close,costs)
    estimated_exit_fee=qty*costs.sell_price(bars[end-1].close)*costs.fee_bps/10000
    return RunResult(str(starting_balance),str(ending),str(ending-starting_balance),
                     float((ending/starting_balance-1)*100),float(dd*100),len(orders),
                     completed,qty>0,str(total_fees),str(estimated_exit_fee),orders)
