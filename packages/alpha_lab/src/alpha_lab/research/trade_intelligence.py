"""Explainable research decisions. No order or execution dependencies."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import isfinite

from alpha_lab.data.adapters.coinbase_candles import (
    BARS_REQUIRED, CLOSE_DELAY, SOURCE, CandleBatch, check_cadence, check_research_window, interval, latest_candle_end, utc,
)
from alpha_lab.research.coinbase_paper_book import PRODUCTS, executable
from alpha_lab.research.paper_market import DEFAULT_COSTS
from alpha_lab.research.promotion_authority import decide_strategy_promotion
from alpha_lab.research.trade_risk import ASSET_CAP, CRYPTO_GROUP_CAP, LIMITS, estimate_round_trip_bps, size_long
from alpha_lab.research.trade_signals import STRATEGY_VERSION, generate_signals

LIVE = "LIVE_PUBLIC"
OFFLINE = "OFFLINE_REPLAY"
RESEARCH_MODE = "RESEARCH_RECOMMENDATIONS"
MIN_OOS_TRADES = 40
MIN_POSITIVE_FOLDS = 3
MAX_OOS_DRAWDOWN = 0.05


@dataclass(frozen=True)
class Evidence:
    """Versioned, exact-regime metrics supplied by a server-owned evaluation."""

    product: str
    timeframe: str
    strategy: str
    version: str
    direction: str
    trend: str
    volatility: str
    window_start: datetime
    window_end: datetime
    benchmark: str
    source: str
    round_trip_bps: Decimal
    trades: int
    folds: int
    positive_folds: int
    mean_net_trade_return: float
    adjusted_lower_per_bar: float | None
    stressed_mean_per_bar: float
    max_drawdown: float
    benchmark_excess_per_bar: float

    @property
    def comparison(self):
        return (self.source, self.timeframe, self.window_start, self.window_end, self.benchmark,
                self.round_trip_bps)


def assess_evidence(record, *, batch, signal, regime, quote, costs):
    if record is None:
        return ("Independent out-of-sample evidence is missing for this exact strategy and regime",)
    if (record.product, record.timeframe, record.strategy, record.version, record.direction,
        record.trend, record.volatility) != (batch.product, batch.timeframe, signal.strategy, STRATEGY_VERSION,
                                             signal.direction, regime.trend, regime.volatility):
        return ("Evidence identity or regime does not match the signal",)
    try:
        check_research_window(record.window_start, record.window_end)
    except ValueError:
        return ("Evidence window is invalid or reserved",)
    if record.source != SOURCE or record.window_end >= batch.end:
        return ("Evidence source or chronological separation is unverified",)
    values = (record.mean_net_trade_return, record.adjusted_lower_per_bar, record.stressed_mean_per_bar,
              record.max_drawdown, record.benchmark_excess_per_bar)
    if not all(type(value) in (float, int) and isfinite(value) for value in values):
        return ("Out-of-sample uncertainty or returns are unavailable",)
    if (record.trades < MIN_OOS_TRADES or record.positive_folds < MIN_POSITIVE_FOLDS
            or record.positive_folds > record.folds or record.positive_folds <= record.folds / 2
            or min(record.mean_net_trade_return, record.adjusted_lower_per_bar, record.stressed_mean_per_bar,
                   record.benchmark_excess_per_bar) <= 0
            or not 0 <= record.max_drawdown <= MAX_OOS_DRAWDOWN):
        return ("Out-of-sample sample size, net expectancy, stress, benchmark or drawdown gate failed",)
    if not isinstance(record.round_trip_bps, Decimal) or not record.round_trip_bps.is_finite():
        return ("Historical cost assumptions are unavailable",)
    if estimate_round_trip_bps(quote, costs) > record.round_trip_bps:
        return ("Current spread and costs exceed the validated cost envelope",)
    authority = decide_strategy_promotion(assessment=asdict(record))
    return () if authority["promotion_authorised"] is True else (authority["reason"],)


def _committee(signal, regime, quality, evidence_reasons, risk_reasons, decision):
    bull = signal.reason if signal.direction == "LONG" else "No long thesis from this rule"
    bear = signal.reason if signal.direction == "SHORT" else "A long thesis remains exposed to reversal and gaps"
    sceptic = [*evidence_reasons, *risk_reasons]
    if regime.volatility == "HIGH":
        sceptic.append("Volatility is elevated relative to the preceding ATR baseline")
    if signal.stability == 1:
        sceptic.append("Direction was first observed on the latest completed candle")
    return {
        "mode": "DETERMINISTIC_ADVISORY",
        "market_intelligence": quality,
        "technical_analysis": list(regime.reasons),
        "quantitative_research": list(evidence_reasons) or ["Evidence gates passed"],
        "bull_case": bull,
        "bear_case": bear,
        "sceptic": sceptic or [signal.invalidation],
        "portfolio": list(risk_reasons) or ["Read-only portfolio review. No order submitted."],
        "decision": decision,
        "independent_risk": list(risk_reasons) or ["Risk gate is evaluated for qualified long proposals only"],
    }


def _as_market(product, quote, batch, healthy, now, timeframe, provider_state):
    fresh = (healthy is True and executable(quote, now) and quote.symbol == product
             and quote.exchange_at <= now)
    seconds, _ = interval(timeframe)
    complete = (isinstance(batch, CandleBatch) and batch.product == product and batch.timeframe == timeframe
                and len(batch.bars) == BARS_REQUIRED and batch.end == latest_candle_end(now, timeframe)
                and batch.bars[-1].time + timedelta(seconds=seconds) == batch.end)
    if complete:
        try:
            check_research_window(batch.bars[0].time, batch.end)
            check_cadence(batch.bars, seconds)
        except ValueError:
            complete = False
    quality = ("PROVIDER_RATE_LIMITED" if provider_state == "PROVIDER_RATE_LIMITED" else
               "VALIDATED" if fresh and complete else
               "BOOK_UNAVAILABLE" if not fresh else "CANDLES_UNAVAILABLE")
    return {
        "product": product, "data_quality": quality, "book_fresh": fresh, "candles_fresh": complete,
        "mid": str(quote.mid) if fresh else None, "bid": str(quote.bid) if fresh else None,
        "ask": str(quote.ask) if fresh else None, "book_source": quote.source if fresh else None,
        "book_event_utc": quote.exchange_at.isoformat() if fresh else None,
        "book_received_utc": quote.observed_at.isoformat() if fresh else None,
        "book_sequence": quote.source_sequence if fresh else None,
        "book_age_seconds": (now - quote.exchange_at).total_seconds() if fresh else None,
        "spread_bps": str((quote.ask - quote.bid) / quote.mid * 10000) if fresh else None,
        "candle_source": batch.source if complete else None, "candle_sha256": batch.sha256 if complete else None,
        "candle_close_utc": batch.end.isoformat() if complete else None,
    }


def analyse_trade_intelligence(*, now, quotes, healthy, batches, rules, risk=None, evidence=(),
                               costs=DEFAULT_COSTS, timeframe="4h", mode=LIVE, provider_state="PUBLIC"):
    """Evaluate BTC/ETH/SOL without arming, placing or altering simulated orders."""
    now = utc(now)
    seconds, _ = interval(timeframe)
    if mode not in (LIVE, OFFLINE):
        raise ValueError("explicit live or replay mode required")
    markets, qualified = [], []
    for product in PRODUCTS:
        quote, batch = quotes.get(product), batches.get(product)
        market = _as_market(product, quote, batch, healthy.get(product), now, timeframe, provider_state)
        market.update({"regime": None, "candidates": [], "decision": "HALT"})
        markets.append(market)
        if not market["candles_fresh"]:
            continue
        if mode == LIVE and batch.source != SOURCE:
            market["data_quality"] = "REPLAY_DATA_REJECTED"
            continue
        regime, signals = generate_signals(batch.bars)
        market["regime"] = {k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(regime).items()}
        for signal in signals:
            plan, validation, evidence_reasons, risk_reasons = None, "UNVERIFIED", (), ()
            record = None
            if market["data_quality"] != "VALIDATED":
                decision = "HALT"
                risk_reasons = ("Fresh validated candles and source books are required",)
            elif signal.direction == "FLAT":
                decision = "FLAT"
                evidence_reasons = (signal.reason,)
            elif signal.direction == "SHORT":
                decision = "UNSUPPORTED"
                risk_reasons = ("USD spot paper trading has no short-entry facility",)
            elif mode != LIVE or regime.trend == "UNCERTAIN":
                decision = "UNVERIFIED"
                evidence_reasons = ("Replay data or an uncertain market regime cannot support a recommendation",)
            else:
                matches = [item for item in evidence
                           if (item.product, item.timeframe, item.strategy, item.direction, item.trend,
                               item.volatility) == (product, timeframe, signal.strategy, signal.direction,
                                                    regime.trend, regime.volatility)]
                record = matches[0] if len(matches) == 1 else None
                evidence_reasons = assess_evidence(record, batch=batch, signal=signal, regime=regime,
                                                   quote=quote, costs=costs)
                decision = "UNVERIFIED"
                if not evidence_reasons:
                    validation = "VERIFIED_RESEARCH"
                    plan, risk_reasons = size_long(
                        quote=quote, rules=rules.get(product), regime=regime, risk=risk, now=now,
                        signal_at=batch.end, interval_seconds=seconds, costs=costs)
                    decision = "LONG" if plan else "HALT"

            candidate = {
                "product": product, "strategy": signal.strategy, "version": STRATEGY_VERSION,
                "direction": signal.direction, "decision": decision, "signal_close_utc": batch.end.isoformat(),
                "signal_available_utc": (batch.end + CLOSE_DELAY).isoformat(),
                "regime": regime.trend, "volatility": regime.volatility, "data_quality": market["data_quality"],
                "reason": signal.reason, "invalidation": signal.invalidation,
                "stability_completed_bars": signal.stability, "validation": validation,
                "validation_reasons": evidence_reasons, "risk_reasons": risk_reasons, "plan": plan,
                "evidence": ({k: v.isoformat() if isinstance(v, datetime) else str(v) if isinstance(v, Decimal)
                              else None if type(v) is float and not isfinite(v) else v
                              for k, v in asdict(record).items()} if record is not None else None),
                "committee": _committee(signal, regime, market["data_quality"], evidence_reasons,
                                        risk_reasons, decision),
            }
            market["candidates"].append(candidate)
            if plan:
                key = (record.adjusted_lower_per_bar, record.mean_net_trade_return, -record.max_drawdown,
                       signal.stability, -regime.atr_fraction, -Decimal(market["spread_bps"]), quote.ask_size * quote.ask)
                qualified.append((record.comparison, key, candidate))
        decisions = {c["decision"] for c in market["candidates"]}
        market["decision"] = next(d for d in ("LONG", "HALT", "UNVERIFIED", "UNSUPPORTED", "FLAT") if d in decisions)

    comparable = len({comparison for comparison, _, _ in qualified}) <= 1
    ranking = []
    if comparable:
        ranked_assets = set()
        for _, _, candidate in sorted(qualified, key=lambda item: item[1], reverse=True):
            if candidate["product"] not in ranked_assets:
                ranked_assets.add(candidate["product"])
                ranking.append({"rank": len(ranking) + 1, "product": candidate["product"],
                                "strategy": candidate["strategy"], "decision": candidate["decision"]})
    return {
        "mode": RESEARCH_MODE, "data_mode": mode, "timeframe": timeframe, "currency": "USD",
        "as_of_utc": now.isoformat(), "decision": "RESEARCH OPPORTUNITY" if qualified else "NO TRADE",
        "market_data": "REPLAY" if mode == OFFLINE else provider_state, "markets": markets, "ranking": ranking,
        "ranking_basis": ("Adjusted net lower bound, expectancy, drawdown, signal stability, volatility, spread and depth"
                          if comparable else "Evidence windows or costs are incomparable"),
        "portfolio_risk": {
            "status": "UNAVAILABLE" if risk is None else risk.halt_reason or "RECONCILED",
            "open_stop_risk_fraction": (str(risk.open_stop_risk / risk.nav) if risk and risk.nav > 0 else None),
            "max_aggregate_stop_risk_fraction": str(LIMITS.max_aggregate_risk_pct),
            "asset_concentration_limit_fraction": str(ASSET_CAP),
            "correlated_crypto_limit_fraction": str(CRYPTO_GROUP_CAP),
        },
        "automated_paper_execution": False, "real_money_execution": False,
    }


def owner_recommendations(paper, candle_feed, evidence=()):
    now = paper.clock()
    quotes, healthy, _ = paper.feed.snapshot(now)
    batches, rules, status = candle_feed.snapshot(now)
    risk = paper.recommendation_context(now, quotes, healthy)
    # A dependency check may outlast a book's freshness. Use the same snapshot,
    # rechecked at the response time, and never replace it with newer quotes.
    return analyse_trade_intelligence(now=paper.clock(), quotes=quotes, healthy=healthy, batches=batches,
                                      rules=rules, risk=risk, costs=paper.costs, evidence=evidence,
                                      timeframe=candle_feed.timeframe, provider_state=status)


def utc_now():
    return datetime.now(timezone.utc)
