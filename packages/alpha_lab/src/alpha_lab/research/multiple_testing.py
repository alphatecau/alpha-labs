"""Descriptive dependence-aware bounds on paired daily equity changes."""
from itertools import accumulate
from math import ceil, fsum
from random import Random


def paired_daily_excess_bps(bars, candidate, comparator, capital, annual_overhead) -> list[float]:
    """Use full UTC days only. Curves include one mark per contiguous hourly bar."""
    if len(bars) != len(candidate) or len(bars) != len(comparator):
        raise ValueError("Mismatched benchmark curves")
    excess = [new - old for new, old in zip(candidate, comparator)]
    daily_cost = annual_overhead / 365
    daily = []
    for i, bar in enumerate(bars):
        if i < 23 or bar.time.hour != 23:
            continue
        prior_excess = excess[i - 24] if i >= 24 else 0
        daily.append(float((excess[i] - prior_excess - daily_cost) / capital * 10_000))
    return daily


def moving_block_lower_bound(daily: list[float], *, block_days: int,
                             minimum_blocks: int, replicates: int, seed: int,
                             family_alpha: float, comparisons: int) -> dict:
    """One-sided Bonferroni-adjusted percentile bound for a fixed comparison family."""
    days = len(daily)
    blocks, tail = divmod(days, block_days)
    alpha = family_alpha / comparisons
    result = {
        "complete_utc_days": days,
        "whole_blocks_in_sample": blocks,
        "mean_daily_excess_bps": fsum(daily) / days if days else None,
        "per_comparison_alpha": alpha,
        "lower_daily_excess_bps": None,
    }
    if blocks < minimum_blocks:
        return result

    prefix = list(accumulate(daily, initial=0.0))
    sums = [prefix[i + block_days] - prefix[i] for i in range(days - block_days + 1)]
    rng = Random(seed)
    draws = []
    for _ in range(replicates):
        block_starts = [rng.randrange(len(sums)) for _ in range(blocks)]
        resampled_sum = fsum(sums[i] for i in block_starts)
        if tail:
            i = rng.randrange(days - tail + 1)
            resampled_sum += prefix[i + tail] - prefix[i]
        draws.append(resampled_sum / days)
    draws.sort()
    result["lower_daily_excess_bps"] = draws[ceil(replicates * alpha) - 1]
    return result
