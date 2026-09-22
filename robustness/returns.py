"""Return primitives (spec decision 2): per-contract % return for timing tests, $ P&L per
fixed 1 contract for money tests, and the matched drift baseline - the exact expectation
of a random entry with the same hold and direction (spec decision 5)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def pct_returns(trades: pd.DataFrame) -> np.ndarray:
    """direction x (exit_price / entry_price - 1) per trade, using the actual fills."""
    return trades.direction.to_numpy() * (trades.exit_price.to_numpy() / trades.entry_price.to_numpy() - 1.0)


def usd_per_contract(trades: pd.DataFrame, point_value: float) -> np.ndarray:
    """direction x (exit - entry) x point_value per trade: gross $ for ONE contract, ignoring
    the report's position sizing."""
    return trades.direction.to_numpy() * (trades.exit_price.to_numpy() - trades.entry_price.to_numpy()) * point_value


def forward_open_returns(open_: np.ndarray, hold: int) -> np.ndarray:
    """open[j+hold] / open[j] - 1 for every entry bar j with j+hold inside the series
    (length len(open_) - hold). Mirrors a next-bar-at-market entry and exit."""
    if hold < 1 or hold >= len(open_):
        raise ValueError(f"hold {hold} outside 1..{len(open_) - 1}")
    return open_[hold:] / open_[:-hold] - 1.0


@dataclass
class MatchedBaseline:
    """Per-trade arrays: mean = expected return of a random entry with that trade's hold and
    direction; win_rate = probability such a random entry is profitable."""
    mean: np.ndarray
    win_rate: np.ndarray


def matched_drift_baseline(open_: np.ndarray, holds: np.ndarray, directions: np.ndarray,
                           mask: np.ndarray | None = None) -> MatchedBaseline:
    """Deterministic baseline: for each distinct hold H, the mean (and positive share) of
    forward_open_returns over all candidate entry bars j (optionally only those with
    mask[j] True). A short trade's baseline is minus the long mean; its win rate is the
    share of negative forward returns. NaN where the mask leaves no candidate bar."""
    holds = np.asarray(holds, dtype=int)
    directions = np.asarray(directions, dtype=float)
    n = len(open_)
    mean = np.empty(len(holds)); win = np.empty(len(holds))
    for h in np.unique(holds):
        fwd = forward_open_returns(open_, int(h))
        m = np.ones(n - h, dtype=bool) if mask is None else np.asarray(mask, dtype=bool)[: n - h]
        sel = holds == h
        if not m.any():
            mean[sel] = np.nan; win[sel] = np.nan
            continue
        f = fwd[m]
        mu, p_up, p_dn = float(f.mean()), float((f > 0).mean()), float((f < 0).mean())
        mean[sel] = directions[sel] * mu
        win[sel] = np.where(directions[sel] > 0, p_up, p_dn)
    return MatchedBaseline(mean=mean, win_rate=win)
