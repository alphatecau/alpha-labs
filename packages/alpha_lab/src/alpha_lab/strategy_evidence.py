"""Fail-closed, execution-free validation of a chronological net-return series.

This module evaluates supplied *out-of-sample* per-period returns only.
It cannot certify profitability, data provenance, or independence of samples.
"""
from dataclasses import dataclass
from math import isfinite, sqrt
from random import Random
from statistics import mean, stdev

@dataclass(frozen=True)
class ValidationConfig:
    min_observations: int = 120
    min_trades: int = 40
    min_positive_folds: int = 3
    block_size: int = 8
    bootstrap_draws: int = 1000
    confidence: float = 0.95
    seed: int = 42

@dataclass(frozen=True)
class ValidationResult:
    status: str
    reasons: tuple[str, ...]
    observations: int
    trades: int
    positive_folds: int
    total_folds: int
    mean_net_return: float | None
    lower_confidence_bound: float | None
    max_drawdown: float | None
    stress_mean_net_return: float | None

def _drawdown(returns: tuple[float, ...]) -> float:
    wealth = peak = 1.0
    worst = 0.0
    for r in returns:
        wealth *= 1.0 + r
        peak = max(peak, wealth)
        worst = max(worst, 1.0 - wealth / peak)
    return worst

def evaluate_oos(
    net_period_returns: tuple[float, ...],
    *, trades: int,
    fold_net_returns: tuple[float, ...],
    additional_cost_per_period: float,
    config: ValidationConfig = ValidationConfig(),
) -> ValidationResult:
    if (not isinstance(config.min_observations, int) or config.min_observations < 2
        or not isinstance(config.min_trades, int) or config.min_trades < 1
        or not isinstance(config.min_positive_folds, int) or config.min_positive_folds < 1
        or not isinstance(config.block_size, int) or config.block_size < 1
        or not isinstance(config.bootstrap_draws, int) or config.bootstrap_draws < 100
        or not 0.5 < config.confidence < 1.0):
        raise ValueError("Invalid validation configuration")
    if not isinstance(trades, int) or isinstance(trades, bool) or trades < 0:
        raise ValueError("Invalid trade count")
    if not isinstance(net_period_returns, tuple) or not isinstance(fold_net_returns, tuple):
        raise ValueError("Returns must be immutable tuples")
    if (not net_period_returns or not fold_net_returns or
        any(not isinstance(x, (int, float)) or not isfinite(x) or x <= -1
            for x in net_period_returns + fold_net_returns)):
        raise ValueError("Invalid or missing return observations")
    if not isfinite(additional_cost_per_period) or additional_cost_per_period < 0:
        raise ValueError("Invalid cost stress")
    n = len(net_period_returns)
    positive = sum(x > 0 for x in fold_net_returns)
    stress = tuple(r - additional_cost_per_period for r in net_period_returns)
    if any(r <= -1 for r in stress):
        raise ValueError("Cost stress produces impossible period return")
    reasons = []
    if n < config.min_observations:
        reasons.append("INSUFFICIENT_OBSERVATIONS")
    if trades < config.min_trades:
        reasons.append("INSUFFICIENT_TRADES")
    if positive < config.min_positive_folds or positive <= len(fold_net_returns) / 2:
        reasons.append("INSUFFICIENT_POSITIVE_FOLDS")
    if len(fold_net_returns) < 3:
        reasons.append("INSUFFICIENT_FOLDS")
    if config.block_size > n:
        reasons.append("BLOCK_EXCEEDS_HISTORY")
    lower = None
    if n >= 2 and config.block_size <= n:
        rng = Random(config.seed)
        blocks = []
        for _ in range(config.bootstrap_draws):
            sample = []
            while len(sample) < n:
                start = rng.randrange(n)
                sample.extend(net_period_returns[(start + j) % n]
                              for j in range(config.block_size))
            blocks.append(mean(sample[:n]))
        blocks.sort()
        idx = max(0, int((1 - config.confidence) * len(blocks)) - 1)
        lower = blocks[idx]
        if lower <= 0:
            reasons.append("NONPOSITIVE_BOOTSTRAP_LOWER_BOUND")
    if mean(stress) <= 0:
        reasons.append("NONPOSITIVE_COST_STRESS")
    # A positive screen is a research candidate only, never promotion approval.
    status = "REJECT" if reasons else "REVIEW_REQUIRED"
    return ValidationResult(status, tuple(reasons), n, trades, positive,
                            len(fold_net_returns), mean(net_period_returns),
                            lower, _drawdown(net_period_returns), mean(stress))
