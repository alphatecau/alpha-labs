"""Evaluation utilities. Report results; never treat point estimates as proof of alpha."""
from decimal import Decimal
import hashlib
import json
from alpha_lab.research.strategies.momentum import ema_signal
from alpha_lab.backtest.costs import CostModel
from alpha_lab.backtest.engine import replay

def evaluate(dataset, *, fast=12, slow=48, starting_balance=Decimal('10000'),
             max_allocation=Decimal('0.20'), fee_bps=Decimal('10'),slippage_bps=Decimal('10')):
    bars=dataset.bars
    if not 1<fast<slow or slow>=len(bars)//2: raise ValueError('Incompatible strategy horizons and dataset length')
    # Fixed chronological split; holdout cannot be used to tune parameter choices.
    split=int(len(bars)*Decimal('0.70'))
    if split<=slow+2 or len(bars)-split<15:raise ValueError('Insufficient train/holdout data')
    signals=ema_signal([b.close for b in bars],fast,slow)
    base=CostModel(fee_bps,slippage_bps)
    periods={'training':(slow+1,split),'holdout':(split,len(bars))}
    results={}
    for name,(start,end) in periods.items():
        strategy=replay(bars,signals,start,end,starting_balance=starting_balance,max_allocation=max_allocation,costs=base)
        stress=replay(bars,signals,start,end,starting_balance=starting_balance,max_allocation=max_allocation,costs=base.twice())
        passive=replay(bars,signals,start,end,starting_balance=starting_balance,max_allocation=max_allocation,costs=base,passive=True)
        results[name]={'strategy':strategy.__dict__,'double_cost_strategy':stress.__dict__,
                       'equal_allocation_buy_hold':passive.__dict__,
                       'excess_vs_buy_hold_pct_points':strategy.return_pct-passive.return_pct}
    config={'model_version':'0.1.0-offline-ema', 'fast':fast,'slow':slow,'starting_balance':str(starting_balance),
            'max_allocation':str(max_allocation),'fee_bps':str(fee_bps),'slippage_bps':str(slippage_bps)}
    config_hash=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    return {'status':'HYPOTHESIS_SCREEN_ONLY_NOT_VALIDATED_ALPHA',
            'configuration_sha256':config_hash,'configuration':config,
            'dataset':{'sha256':dataset.sha256,'provenance':dataset.provenance,'quote_currency':dataset.quote_currency,
                       'interval_minutes':dataset.interval_minutes,'bars':len(bars),'split_index':split},
            'assumptions':{'strategy':'EMA_TREND_LONG_ONLY','fast':fast,'slow':slow,'fee_bps_each_side':str(fee_bps),
                           'adverse_slippage_bps_each_side':str(slippage_bps),'max_capital_allocation':str(max_allocation),
                           'starting_balance_quote_units':str(starting_balance),'order_fills':'next_candle_open_modelled',
                           'position_mark':'liquidation_estimate_at_last_close','operating_costs':'not_included',
                           'latency_funding_MEV_and_adverse_selection':'not_modelled','trade_entry_decision':'prior_candle_close'},
            'periods':results,
            'limitations':['Historical CSV is not independently verified or executable pricing',
                           'Holdout is descriptive until strategy design and preprocessing are frozen externally',
                           'Candle prices do not model spread/depth/intra-bar execution failures',
                           'No statistical confidence bound or multiple-testing adjustment',
                           'Funding, tax, and operating expenses are excluded; value is in quote units, not AUD FX unless quote is AUD',
                           'No live market data, orders, custody, autonomous agents, or AI calls']}
