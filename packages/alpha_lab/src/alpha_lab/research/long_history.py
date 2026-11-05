"""Reproducible historical long/flat research; NEVER a trading signal.

Preserves the frozen EMA(12,48) hypothesis and legacy research engine.
Three chronological partitions and a 48-candle embargo are descriptive;
freely rerunnable local tests cannot establish independently sealed alpha.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import timedelta
import hashlib
import json
from math import sqrt, isfinite
from pathlib import Path
from statistics import mean, stdev

from alpha_lab.backtest.costs import CostModel
from alpha_lab.backtest.engine import replay
from alpha_lab.data.csv_import import load_csv
from alpha_lab.data.adapters.binance_archive import verify_dataset
from alpha_lab.research.strategies.momentum import ema_signal
from alpha_lab.research.walk_forward import evaluate_windows

HOURS_YEAR = 365 * 24
FROZEN_MODEL = "EMA_12_48_FROZEN_LONG_FLAT"
SCHEMA = "alpha-labs.long-history-experiment.v1"
STATUS = "EXPLORATORY_HISTORICAL_MODELLED_ONLY_NO_VALIDATED_ALPHA"


def _number(value, label: str, *, zero: bool = True) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"Invalid {label}")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {label}") from exc
    if not n.is_finite() or (n < 0 if zero else n <= 0):
        raise ValueError(f"Invalid {label}")
    return n


def default_config() -> dict:
    return {"strategy": FROZEN_MODEL, "fast": 12, "slow": 48,
            "capital_usdt": "10000", "max_allocation": "0.20",
            "fee_bps_each_side": "10", "slippage_bps_each_side": "10",
            "operating_cost_usdt_per_year": "0", "embargo_candles": 48,
            "training_fraction": "0.60", "validation_fraction": "0.20"}


def _config(cfg: dict) -> dict:
    expected = default_config()
    if not isinstance(cfg, dict) or set(cfg) != set(expected):
        raise ValueError("Frozen experiment configuration shape changed")
    if cfg["strategy"] != FROZEN_MODEL or type(cfg["fast"]) is not int or cfg["fast"] != 12 or type(cfg["slow"]) is not int or cfg["slow"] != 48:
        raise ValueError("EMA strategy must remain the frozen 12/48 baseline")
    if type(cfg["embargo_candles"]) is not int or cfg["embargo_candles"] < 48:
        raise ValueError("Required embargo is at least 48 completed hourly candles")
    if _number(cfg["training_fraction"], "training fraction") != Decimal("0.60") or _number(cfg["validation_fraction"], "validation fraction") != Decimal("0.20"):
        raise ValueError("Chronological fractions must be 60/20/20")
    capital = _number(cfg["capital_usdt"], "capital", zero=False)
    allocation = _number(cfg["max_allocation"], "allocation", zero=False)
    if allocation > 1 or capital <= 0:
        raise ValueError("Invalid capital allocation")
    for k in ("fee_bps_each_side", "slippage_bps_each_side"):
        if _number(cfg[k], k) > 1000:
            raise ValueError("Implausible friction model")
    _number(cfg["operating_cost_usdt_per_year"], "operating expense")
    # CostModel rejects invalid 2x stress assumptions.
    base = CostModel(_number(cfg["fee_bps_each_side"], "fee"),
                     _number(cfg["slippage_bps_each_side"], "slippage"))
    base.twice()
    return cfg


def _fingerprint(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def freeze_experiment(data_csv: Path, manifest_json: Path, output: Path,
                      config: dict | None = None) -> dict:
    """Create an immutable-once-written local configuration record.

    File permissions are NOT a cryptographic seal or independent registration.
    """
    config = _config(config or default_config())
    manifest = verify_dataset(data_csv, manifest_json)
    if Path(output).exists():
        raise FileExistsError("Refusing to overwrite an existing experiment specification")
    body = {"schema": SCHEMA, "data_sha256": manifest["csv_sha256"],
            "symbol": manifest["symbol"], "manifest_sha256": hashlib.sha256(Path(manifest_json).read_bytes()).hexdigest(),
            "configuration": config, "trading_enabled": False,
            "holdout_independently_sealed": False}
    body["specification_sha256"] = _fingerprint(body)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidentally replacing the frozen local spec.
    with output.open("x", encoding="utf-8") as dest:
        dest.write(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return body


def _read_spec(data_csv: Path, manifest_json: Path, spec_file: Path) -> tuple[dict, dict]:
    spec = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    if spec.get("schema") != SCHEMA or spec.get("trading_enabled") is not False or spec.get("holdout_independently_sealed") is not False:
        raise ValueError("Unsupported or misleading experiment specification")
    digest = spec.get("specification_sha256")
    unsigned = {k: v for k, v in spec.items() if k != "specification_sha256"}
    if digest != _fingerprint(unsigned):
        raise ValueError("Experiment specification modified")
    manifest = verify_dataset(data_csv, manifest_json)
    if (spec.get("data_sha256") != manifest["csv_sha256"] or
        spec.get("symbol") != manifest["symbol"] or
        spec.get("manifest_sha256") != hashlib.sha256(Path(manifest_json).read_bytes()).hexdigest()):
        raise ValueError("Experiment/data manifest mismatch")
    _config(spec.get("configuration"))
    return spec, manifest


def _risk_stats(equity: list[float], start_equity: float) -> dict:
    if not equity or start_equity <= 0 or not all(isfinite(x) and x > 0 for x in equity):
        raise ValueError("Invalid equity curve")
    returns = []
    prior = start_equity
    peak = prior
    dd = 0.0
    for nav in equity:
        returns.append(nav / prior - 1)
        prior = nav
        peak = max(peak, nav)
        dd = max(dd, (peak - nav) / peak)
    mu = mean(returns)
    # Sample-volatility annualisation treats hourly returns as iid; this is
    # an assumption, not proof of valid high-frequency Sharpe estimates.
    vol = stdev(returns) if len(returns) > 1 else 0
    downside = sqrt(sum(min(r, 0.0) ** 2 for r in returns) / len(returns))
    annual = (equity[-1] / start_equity) ** (HOURS_YEAR / len(equity)) - 1
    return {
        "annualised_return_pct": 100 * annual,
        "annualised_volatility_pct": 100 * vol * sqrt(HOURS_YEAR),
        "sharpe_zero_risk_free": mu / vol * sqrt(HOURS_YEAR) if vol > 1e-14 else None,
        "sortino_zero_target": mu / downside * sqrt(HOURS_YEAR) if downside > 1e-14 else None,
        "max_drawdown_pct": dd * 100,
        "calmar": annual / dd if dd > 1e-14 else None,
    }


def _window(bars, signals, start: int, end: int, costs: CostModel,
            capital: Decimal, allocation: Decimal, *, passive: bool) -> dict:
    """Cost-adjusted hourly NAV and per-period P&L; no orders are ever sent."""
    cash, qty = capital, Decimal(0)
    fees, slip_total, volume = Decimal(0), Decimal(0), Decimal(0)
    orders = 0
    exposed = 0
    curve = []
    for i in range(start, end):
        bar = bars[i]
        should_hold = ((i == start or qty > 0) if passive else signals[i - 1])
        if should_hold and qty == 0:
            buy_budget = min(cash, capital * allocation)
            units = costs.buy_quantity(buy_budget, bar.open)
            execution_price = costs.buy_price(bar.open)
            nominal = units * execution_price
            fee = nominal * costs.fee_bps / 10000
            outlay = nominal + fee
            if units < 0 or outlay > cash + Decimal("1e-15"):
                raise ValueError("Accounting invariant failed on entry")
            cash -= outlay
            qty = units
            fees += fee
            slip_total += units * (execution_price - bar.open)
            volume += nominal
            orders += 1
        elif not should_hold and qty > 0:
            execution_price = costs.sell_price(bar.open)
            nominal = qty * execution_price
            fee = nominal * costs.fee_bps / 10000
            cash += nominal - fee
            fees += fee
            slip_total += qty * (bar.open - execution_price)
            volume += nominal
            qty = Decimal(0)
            orders += 1
        if qty > 0:
            exposed += 1
        # Liquidation estimate includes hypothetical, unexecuted exit costs.
        nav = cash + costs.sell_proceeds(qty, bar.close)
        if cash < -Decimal("1e-12") or qty < 0 or nav <= 0:
            raise ValueError("Invalid portfolio state")
        curve.append(float(nav))
    ending = cash + costs.sell_proceeds(qty, bars[end - 1].close)
    stats = _risk_stats(curve, float(capital))
    return {
        "net_modelled_execution_return_pct": float((ending / capital - 1) * 100),
        "final_liquidatable_usdt": str(ending),
        "modelled_fees_usdt": str(fees),
        "modelled_adverse_slippage_usdt": str(slip_total),
        "executed_orders_modelled": orders,
        "open_position": qty > 0,
        "exposure_fraction_of_hours": exposed / len(curve),
        "turnover_to_starting_capital": float(volume / capital),
        "hourly_nav_summary": {"first": curve[0], "last": curve[-1], "observations": len(curve)},
        **stats,
    }


def evaluate_periods(dataset, config: dict | None = None, *, min_bars: int = 2 * HOURS_YEAR) -> dict:
    """Frozen strategy; 60/20/20, 48h gap, same 20% passive benchmark.

    min_bars is injectable for bounded unit fixtures; published CLI always
    calls with the production two-year threshold.
    """
    cfg = _config(config or default_config())
    if dataset.interval_minutes != 60 or dataset.quote_currency != "USDT":
        raise ValueError("Only 1h USDT spot datasets supported")
    n = len(dataset.bars)
    if n < min_bars or n < 400:
        raise ValueError("Insufficient historical coverage")
    t1, t2 = int(n * 0.60), int(n * 0.80)
    gap = cfg["embargo_candles"]
    intervals = {
        "training": (cfg["slow"] + 1, t1),
        "validation": (t1 + gap, t2),
        "test_unsealed": (t2 + gap, n),
    }
    for lo, hi in intervals.values():
        if lo < 1 or hi - lo < 48:
            raise ValueError("Not enough bars after embargo")
    bars = dataset.bars
    # EMA at prior completed close only; no same-open information.
    signals = ema_signal([bar.close for bar in bars], 12, 48)
    capital = _number(cfg["capital_usdt"], "capital", zero=False)
    fraction = _number(cfg["max_allocation"], "allocation", zero=False)
    costs = CostModel(_number(cfg["fee_bps_each_side"], "fee"),
                      _number(cfg["slippage_bps_each_side"], "slippage"))
    overhead = _number(cfg["operating_cost_usdt_per_year"], "overhead")
    periods = {}
    for label, (start, end) in intervals.items():
        strategy = _window(bars, signals, start, end, costs, capital, fraction, passive=False)
        passive = _window(bars, signals, start, end, costs, capital, fraction, passive=True)
        stress = _window(bars, signals, start, end, costs.twice(), capital, fraction, passive=False)
        # Assert parity against repository's original frozen engine.
        legacy = replay(bars, signals, start, end, starting_balance=capital,
                        max_allocation=fraction, costs=costs)
        if (Decimal(strategy["final_liquidatable_usdt"]) != Decimal(legacy.final_liquidatable_value)
                or strategy["executed_orders_modelled"] != legacy.executed_orders
                or Decimal(strategy["modelled_fees_usdt"]) != Decimal(legacy.total_modelled_fees)):
            raise ValueError("Cross-engine ledger/replay parity failure")
        after_overhead = Decimal(strategy["final_liquidatable_usdt"]) - overhead * Decimal(end - start) / Decimal(HOURS_YEAR)
        periods[label] = {
            "start_utc": bars[start].time.isoformat(),
            "end_exclusive_utc": (bars[end - 1].time + timedelta(hours=1)).isoformat(),
            "bars": end - start,
            "modelled_strategy": strategy,
            "matched_initial_allocation_passive": passive,
            "strategy_double_execution_friction": stress,
            "excess_vs_passive_percentage_points": strategy["net_modelled_execution_return_pct"] - passive["net_modelled_execution_return_pct"],
            "assumed_operating_expenses_usdt": str(overhead * Decimal(end - start) / Decimal(HOURS_YEAR)),
            "after_modelled_execution_and_operating_expenses_usdt": str(after_overhead - capital),
            "after_modelled_execution_and_operating_expenses_pct": float((after_overhead / capital - 1) * 100),
            "legacy_ledger_parity": True,
        }
    rolling = evaluate_windows(dataset, initial=720, window=168)
    return {
        "status": STATUS, "trading_enabled": False,
        "quote_currency": "USDT", "dataset_sha256": dataset.sha256,
        "configuration_sha256": _fingerprint(cfg),
        "configuration": cfg,
        "boundaries_index": {k: [a, b] for k, (a, b) in intervals.items()},
        "holdout_independently_sealed": False,
        "statistical_significance_verified": False,
        "replay_ledger_parity_checked": True,
        "rolling_historical_diagnostics": rolling,
        "benchmark": "same_initial_capital_allocation_passive_hold",
        "periods": periods,
        "limitations": [
            "Archive checksums establish source-file integrity but no independent second-venue price validation",
            "Test period is not sealed from repeated inspection; selection after viewing it invalidates independence",
            "Spot long/flat only; no borrowed short exposure, leverage, or funding model",
            "Next-candle-open fills, fixed adverse slippage and fees are hypotheses, not executable bids/asks",
            "No partial fills, spread depth, impact, order rejection, downtime or position size capacity",
            "Sharpe/Sortino annualisation assumes hourly return properties; confidence intervals not established",
            "Comparators match starting allocation, not exposure/risk throughout the window",
            "Performance in USDT, not AUD; crypto/tax/FX conversion not included",
            "Operating cost is an explicit input assumption; tax excluded",
            "Rolling historical folds reset capital per window and do not demonstrate independent strategy re-training",
            "No multiple-testing adjustment, independent risk audit, broker or live order execution",
        ],
    }


def evaluate_spec(data_csv: Path, manifest_json: Path, spec_file: Path,
                  report_file: Path) -> dict:
    spec, manifest = _read_spec(data_csv, manifest_json, spec_file)
    target = Path(report_file)
    if target.exists():
        raise FileExistsError("Refusing to overwrite a previous research report")
    dataset = load_csv(data_csv, quote_currency="USDT", interval_minutes=60,
                       provenance="binance-vision-spot-monthly-archive-digest-checked")
    result = evaluate_periods(dataset, spec["configuration"])
    result["specification_sha256"] = spec["specification_sha256"]
    result["source_archive_months"] = len(manifest["source_archives"])
    result["instrument"] = manifest["symbol"]
    result["archive_sha256_verified"] = True
    result["source_close_timestamp_anomaly_count"] = manifest["source_close_timestamp_anomaly_count"]
    result["source_close_timestamp_anomalies_require_review"] = manifest["source_close_timestamp_anomalies_require_review"]
    if result["source_close_timestamp_anomalies_require_review"]:
        result["limitations"].append(
            "The source contains kline close-time metadata anomalies; review the exact rows and independent evidence before interpreting this backtest"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, sort_keys=True, allow_nan=False)
        fp.write("\n")
    return result
