"""Fail-closed offline risk-constrained breakout replay.

Research simulation only. No broker, credentials, exchange endpoints or live orders.
Signals are from completed 4h candles; next 1h open is earliest entry.
Stop triggers use hourly OHLC, with adverse gap handling; OHLC cannot establish
intrabar order sequence or real executable fills.
"""
from __future__ import annotations
from datetime import timezone
from decimal import Decimal
from alpha_lab.backtest.costs import CostModel
from alpha_lab.data.csv_import import Bar

CAPITAL = Decimal("10000")
MAX_ALLOCATION = Decimal("0.20")
MAX_POSITION_RISK = Decimal("0.0025")
MAX_AGGREGATE_RISK = Decimal("0.01")
DAILY_HALT = Decimal("0.02")
DRAWDOWN_HALT = Decimal("0.05")
STOP_ATR = Decimal("3")
ATR_PERIOD = 14

def _atr_at_completed_four_hour_close(bars: tuple[Bar, ...]) -> list[Decimal | None]:
    """ATR only appears after a complete UTC-aligned 4h candle."""
    result: list[Decimal | None] = [None] * len(bars)
    trs: list[Decimal] = []
    previous_close: Decimal | None = None
    for i in range(3, len(bars), 4):
        group = bars[i-3:i+1]
        if group[0].time.hour % 4 != 0:
            continue
        high = max(b.high for b in group)
        low = min(b.low for b in group)
        close = group[-1].close
        tr = high-low if previous_close is None else max(high-low, abs(high-previous_close), abs(low-previous_close))
        trs.append(tr)
        previous_close = close
        if len(trs) >= ATR_PERIOD:
            result[i] = sum(trs[-ATR_PERIOD:])/Decimal(ATR_PERIOD)
    return result

def replay_breakout_risk(bars: tuple[Bar, ...], signals: list[bool],
                         start: int, end: int, *, capital: Decimal = CAPITAL,
                         costs: CostModel = CostModel()) -> dict:
    if len(signals) != len(bars) or not (1 <= start < end <= len(bars)):
        raise ValueError("Invalid signal length or window")
    if capital <= 0 or not capital.is_finite():
        raise ValueError("Invalid capital")
    for i, bar in enumerate(bars):
        if (bar.time.tzinfo is None or bar.time.utcoffset() != timezone.utc.utcoffset(None)
            or bar.time.minute or bar.time.second or bar.time.microsecond
            or bar.open <= 0 or bar.low <= 0 or bar.high < max(bar.open,bar.close)
            or bar.low > min(bar.open,bar.close) or bar.volume < 0):
            raise ValueError("Invalid hourly UTC OHLCV")
        if i and (bar.time-bars[i-1].time).total_seconds() != 3600:
            raise ValueError("Missing hourly candle")
    atr = _atr_at_completed_four_hour_close(bars)
    cash = capital
    qty = Decimal(0)
    stop: Decimal | None = None
    peak = capital
    max_dd = Decimal(0)
    day = None
    day_start_nav = capital
    daily_block = False
    permanent_halt = False
    orders = []
    nav_curve = []
    fees = Decimal(0)
    closed = 0
    entry_outlay = Decimal(0)
    risk_at_entry = Decimal(0)
    last_atr: Decimal | None = None
    for i in range(start, end):
        bar = bars[i]
        if atr[i-1] is not None:
            last_atr = atr[i-1]
        # Last completed 4h ATR remains available until the next 4h close.
        if bar.time.date() != day:
            day = bar.time.date()
            day_start_nav = cash + costs.sell_proceeds(qty, bar.open)
            daily_block = False
        if qty > 0 and not signals[i-1]:
            px = costs.sell_price(bar.open)
            proceeds = qty*px*(1-costs.fee_bps/10000)
            fee = qty*px*costs.fee_bps/10000
            cash += proceeds; fees += fee
            orders.append({"kind":"SELL","reason":"signal","time":bar.time.isoformat(),"price":str(px),
                           "quantity":str(qty),"quote_received":str(proceeds),"fee":str(fee),
                           "modelled_trade_pnl":str(proceeds-entry_outlay)})
            qty=Decimal(0);stop=None;closed+=1
        # Gap at open crosses the protective stop: cannot fill at the stale stop price.
        if qty > 0 and stop is not None and bar.open <= stop:
            px=costs.sell_price(bar.open)
            proceeds=qty*px*(1-costs.fee_bps/10000)
            fee=qty*px*costs.fee_bps/10000
            cash+=proceeds;fees+=fee
            orders.append({"kind":"SELL","reason":"gap_stop","time":bar.time.isoformat(),"price":str(px),
                           "quantity":str(qty),"quote_received":str(proceeds),"fee":str(fee),
                           "modelled_trade_pnl":str(proceeds-entry_outlay)})
            qty=Decimal(0);stop=None;closed+=1
        # Drawdown/daily suspension checked before entry, including open gaps.
        open_nav = cash + costs.sell_proceeds(qty,bar.open)
        if open_nav > peak: peak=open_nav
        if open_nav <= day_start_nav*(1-DAILY_HALT): daily_block=True
        if open_nav <= peak*(1-DRAWDOWN_HALT): permanent_halt=True
        if (qty == 0 and signals[i-1] and last_atr is not None
            and not daily_block and not permanent_halt):
            distance=STOP_ATR*last_atr
            if distance > 0 and distance < bar.open:
                px=costs.buy_price(bar.open)
                proposed_stop=bar.open-distance
                # Size from worst modelled entry and planned stop execution,
                # including fees/slippage on both sides.
                unit_loss=(px*(1+costs.fee_bps/10000)
                           -costs.sell_price(proposed_stop)*(1-costs.fee_bps/10000))
                if unit_loss > 0:
                    q=min((capital*MAX_POSITION_RISK)/unit_loss,
                          (capital*MAX_ALLOCATION)/(px*(1+costs.fee_bps/10000)),
                          cash/(px*(1+costs.fee_bps/10000)))
                    if q > 0:
                        outlay=q*px*(1+costs.fee_bps/10000)
                        fee=q*px*costs.fee_bps/10000
                        cash-=outlay;qty=q;stop=proposed_stop;entry_outlay=outlay;fees+=fee
                        risk_at_entry=q*unit_loss
                        orders.append({"kind":"BUY","reason":"breakout","time":bar.time.isoformat(),
                                       "price":str(px),"quantity":str(qty),"quote_outlay":str(outlay),
                                       "fee":str(fee),"planned_stop":str(stop),
                                       "planned_loss_including_costs":str(risk_at_entry)})
        # Intrabar stop: assumed fill at stop, not a guaranteed executable quote.
        # The stop is not raised intra-hour using information from that same bar.
        if qty > 0 and stop is not None and bar.low <= stop:
            px=costs.sell_price(stop)
            proceeds=qty*px*(1-costs.fee_bps/10000)
            fee=qty*px*costs.fee_bps/10000
            cash+=proceeds;fees+=fee
            orders.append({"kind":"SELL","reason":"intrabar_stop_modelled","time":bar.time.isoformat(),
                           "price":str(px),"quantity":str(qty),"quote_received":str(proceeds),
                           "fee":str(fee),"modelled_trade_pnl":str(proceeds-entry_outlay)})
            qty=Decimal(0);stop=None;closed+=1
        # Trailing stop updated only after a completed 4h candle.
        if qty > 0 and atr[i] is not None:
            stop=max(stop,bar.close-STOP_ATR*atr[i])
        nav=cash+costs.sell_proceeds(qty,bar.close)
        if nav > peak:peak=nav
        dd=(peak-nav)/peak
        max_dd=max(max_dd,dd)
        if nav <= day_start_nav*(1-DAILY_HALT):daily_block=True
        if dd >= DRAWDOWN_HALT:permanent_halt=True
        if cash < -Decimal("1e-12") or qty < 0 or nav <= 0:
            raise ValueError("Accounting invariant violated")
        nav_curve.append(str(nav))
    final=Decimal(nav_curve[-1])
    return {"schema":"alpha-labs.breakout-risk-replay.v1",
            "starting_balance":str(capital),"final_liquidatable_value":str(final),
            "return_pct":float((final/capital-1)*100),
            "max_drawdown_pct":float(max_dd*100),"executed_orders":len(orders),
            "closed_trades":closed,"open_position":qty>0,
            "total_modelled_fees":str(fees),"orders":orders,"nav_curve":nav_curve,
            "daily_halt_active_at_end":daily_block,"drawdown_halt_active_at_end":permanent_halt,
            "risk_limits_modelled":{"position_planned_risk":"0.25%","aggregate_planned_risk":"1%",
                                    "daily_loss_halt":"2%","drawdown_halt":"5%",
                                    "gross_notional":"<=1x","allocation":"<=20%"},
            "intrabar_sequence_unobservable":True,"real_fills_verified":False,
            "independent_reconciliation_performed":False,"trading_enabled":False,
            "promotion_authorised":False}
