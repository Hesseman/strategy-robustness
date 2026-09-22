"""T3 - temporal robustness (spec decision 6). Four equal-bar-count windows; a trade
belongs to the window of its entry bar; each window's lift is measured against the matched
drift over that window's own bars. Crisis split = entry bar in the top decile of 20-bar
rolling close-to-close volatility. Plus calendar-year $ per contract."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from robustness.returns import matched_drift_baseline


@dataclass
class WindowResult:
    index: int
    start: pd.Timestamp
    end: pd.Timestamp
    n: int
    mean: float | None
    baseline: float | None
    lift: float | None
    win_rate: float | None
    usd_sum: float
    counted: bool


@dataclass
class TemporalResult:
    windows: list[WindowResult]
    windows_positive: int
    windows_total: int
    score: float
    crisis: dict
    yearly: pd.DataFrame
    years_positive: int
    years_total: int


def _subset(open_, entry_mask_bars, sel, holds, directions, pct_ret, min_n):
    """Mean/baseline/lift/win for the trades in `sel`, baseline over bars in `entry_mask_bars`."""
    n = int(sel.sum())
    if n < min_n:
        return n, None, None, None, None
    base = matched_drift_baseline(open_, holds[sel], directions[sel], mask=entry_mask_bars)
    mean = float(pct_ret[sel].mean()); b = float(np.nanmean(base.mean))
    return n, mean, b, mean - b, float((pct_ret[sel] > 0).mean())


def temporal_test(bars: pd.DataFrame, entry_idx: np.ndarray, holds: np.ndarray, directions: np.ndarray,
                  pct_ret: np.ndarray, usd_pc: np.ndarray, exit_times: pd.DatetimeIndex,
                  n_windows: int = 4, min_n: int = 10) -> TemporalResult:
    """Run T3. Windows with fewer than min_n trades are reported but not counted in the score
    (score = positive-lift windows / counted windows, 0.0 when none counted)."""
    open_ = bars.open.to_numpy(); n = len(bars)
    entry_idx = np.asarray(entry_idx, dtype=int); holds = np.asarray(holds, dtype=int)
    directions = np.asarray(directions); pct_ret = np.asarray(pct_ret, dtype=float); usd_pc = np.asarray(usd_pc, dtype=float)
    windows: list[WindowResult] = []
    for k, ch in enumerate(np.array_split(np.arange(n), n_windows), start=1):
        lo, hi = int(ch[0]), int(ch[-1])
        sel = (entry_idx >= lo) & (entry_idx <= hi)
        wmask = np.zeros(n, dtype=bool); wmask[lo: hi + 1] = True
        cnt, mean, b, lift, win = _subset(open_, wmask, sel, holds, directions, pct_ret, min_n)
        windows.append(WindowResult(k, bars.index[lo], bars.index[hi], cnt, mean, b, lift, win,
                                    float(usd_pc[sel].sum()), counted=cnt >= min_n))
    counted = [w for w in windows if w.counted]
    positive = sum(1 for w in counted if w.lift is not None and w.lift > 0)
    score = positive / len(counted) if counted else 0.0

    vol = pd.Series(bars.close.to_numpy()).pct_change().rolling(20, min_periods=1).std().to_numpy()
    q90 = float(np.nanquantile(vol, 0.9))
    crisis_bars = np.nan_to_num(vol, nan=-np.inf) >= q90
    cf = crisis_bars[entry_idx]
    nc, mc, bc, lc, _ = _subset(open_, crisis_bars, cf, holds, directions, pct_ret, min_n)
    nk, mk, bk, lk, _ = _subset(open_, ~crisis_bars, ~cf, holds, directions, pct_ret, min_n)
    crisis = {"q90_vol": q90, "n_crisis_bars": int(crisis_bars.sum()),
              "n_crisis": nc, "mean_crisis": mc, "baseline_crisis": bc, "lift_crisis": lc,
              "n_calm": nk, "mean_calm": mk, "baseline_calm": bk, "lift_calm": lk}

    yearly = (pd.DataFrame({"year": pd.DatetimeIndex(exit_times).year, "usd": usd_pc})
              .groupby("year").agg(usd=("usd", "sum"), n=("usd", "size")).reset_index())
    return TemporalResult(windows, positive, len(counted), score, crisis, yearly,
                          int((yearly.usd > 0).sum()), int(len(yearly)))
