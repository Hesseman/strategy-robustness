"""Baseline card + T8a: the matched-hold random-entry null (spec decision 5).

One null draw = for every real trade i, a uniformly random entry bar j_i, held for that
trade's own hold H_i in its own direction d_i, return d_i x (open[j_i+H_i]/open[j_i] - 1);
the draw's statistic is the mean over trades. p = share of draws >= the observed mean.
The observed mean uses the actual fills. Ported from signal_lab's T8a (fixed horizon) to
variable per-trade holds; the deterministic baseline is the null's expectation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from robustness.returns import matched_drift_baseline


@dataclass
class RandomEntryResult:
    n_trades: int
    observed_mean: float
    baseline_mean: float
    lift: float
    observed_win_rate: float
    baseline_win_rate: float
    null: np.ndarray
    null_mean: float
    null_std: float
    z: float
    k_ge: int
    n_perm: int
    p_value: float


def random_entry_test(open_: np.ndarray, holds: np.ndarray, directions: np.ndarray,
                      observed: np.ndarray, n_perm: int = 1000, seed: int = 0,
                      chunk: int = 200) -> RandomEntryResult:
    """Run the null. open_: bar opens; holds: per-trade hold in bars (>= 1, < len(open_));
    directions: +1/-1; observed: per-trade % returns (actual fills). Deterministic for a
    given seed. Raises ValueError when a hold does not fit inside the series."""
    open_ = np.asarray(open_, dtype=float)
    holds = np.asarray(holds, dtype=int)
    d = np.asarray(directions, dtype=float)
    observed = np.asarray(observed, dtype=float)
    n = len(open_)
    if holds.min() < 1 or holds.max() >= n:
        raise ValueError("every hold must be >= 1 bar and shorter than the bar series")
    rng = np.random.default_rng(seed)
    span = (n - holds).astype(float)  # valid entry bars j in [0, n - h)
    null = np.empty(n_perm)
    for a in range(0, n_perm, chunk):
        b = min(a + chunk, n_perm)
        u = rng.random((b - a, len(holds)))
        j = np.minimum((u * span).astype(int), n - holds - 1)
        r = d * (open_[j + holds] / open_[j] - 1.0)
        null[a:b] = r.mean(axis=1)
    base = matched_drift_baseline(open_, holds, d)
    obs_mean = float(observed.mean())
    null_mean = float(null.mean())
    null_std = float(null.std(ddof=1)) if n_perm > 1 else float("nan")
    k = int((null >= obs_mean).sum())
    base_mean = float(np.nanmean(base.mean))
    return RandomEntryResult(
        n_trades=len(holds), observed_mean=obs_mean, baseline_mean=base_mean, lift=obs_mean - base_mean,
        observed_win_rate=float((observed > 0).mean()), baseline_win_rate=float(np.nanmean(base.win_rate)),
        null=null, null_mean=null_mean, null_std=null_std,
        z=(obs_mean - null_mean) / null_std if null_std > 0 else float("nan"),
        k_ge=k, n_perm=n_perm, p_value=k / n_perm)
