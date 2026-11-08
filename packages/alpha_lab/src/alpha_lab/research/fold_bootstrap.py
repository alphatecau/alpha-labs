"""Fold-aware moving-block bootstrap for *diagnostic* research only.

Resamples independently inside each fold, never creates blocks crossing fold
boundaries, and retains each fold's original observation weight. It cannot
correct selection bias, overlapping training windows or unsealed holdouts.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from random import Random
from statistics import mean

@dataclass(frozen=True)
class FoldBootstrapResult:
    lower_confidence_bound: float
    mean_period_return: float
    observations: int
    folds: int
    draws: int
    block_size: int
    confidence: float
    boundary_crossings: int = 0

def fold_aware_bootstrap(folds: tuple[tuple[float, ...], ...], *,
                         block_size: int = 8, draws: int = 1000,
                         confidence: float = 0.95, seed: int = 42) -> FoldBootstrapResult:
    if not isinstance(folds, tuple) or not folds or any(not isinstance(f, tuple) or not f for f in folds):
        raise ValueError("Nonempty immutable fold return tuples required")
    if (not isinstance(block_size, int) or isinstance(block_size, bool) or block_size < 1
        or not isinstance(draws, int) or isinstance(draws, bool) or draws < 100
        or not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
        or not isfinite(confidence) or not 0.5 < confidence < 1
        or not isinstance(seed, int) or isinstance(seed, bool)):
        raise ValueError("Invalid bootstrap configuration")
    for fold in folds:
        if len(fold) < block_size:
            raise ValueError("Fold shorter than bootstrap block")
        if any(not isinstance(r, (int, float)) or isinstance(r, bool)
               or not isfinite(r) or r <= -1 for r in fold):
            raise ValueError("Invalid period return")
    rng = Random(seed)
    total = sum(map(len, folds))
    samples = []
    for _ in range(draws):
        accumulated = 0.0
        for fold in folds:
            n = len(fold)
            generated = 0
            while generated < n:
                start = rng.randrange(n)
                count = min(block_size, n - generated)
                accumulated += sum(fold[(start + offset) % n] for offset in range(count))
                generated += count
        samples.append(accumulated / total)
    samples.sort()
    index = max(0, int((1 - confidence) * draws) - 1)
    return FoldBootstrapResult(samples[index],
                               sum(sum(fold) for fold in folds) / total,
                               total, len(folds), draws, block_size, confidence)
