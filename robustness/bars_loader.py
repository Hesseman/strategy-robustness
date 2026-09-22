"""Load a TradeStation Data Window bar export.

Only reason to change: TradeStation changes that export. Two known layouts share
``Date,Time,Open,High,Low,Close``: intraday adds ``Up,Down`` (tick volume up/down),
native daily adds ``Vol,OI`` with ``Time`` always 16:00. Indicator ``PLOTn`` columns
may trail either layout and are dropped. Timestamps are the workspace's own clock and
are kept tz-naive: the report's Trades List uses the same clock, so the join is exact.
"""
from __future__ import annotations

import io

import pandas as pd

REQUIRED = ("Date", "Time", "Open", "High", "Low", "Close")


class BarsFormatError(ValueError):
    """The text is not a TradeStation Data Window export this app can read."""


def load_bars(text: str) -> pd.DataFrame:
    """Return bars with a tz-naive DatetimeIndex named 'ts' (sorted, unique) and float
    columns open/high/low/close/volume (volume = Up+Down, else Vol, else NaN).
    Raises BarsFormatError on missing columns, duplicate timestamps, non-positive prices,
    or fewer than two bars."""
    df = pd.read_csv(io.StringIO(text), skipinitialspace=True)
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise BarsFormatError(f"bar file is missing columns {missing}; expected a TradeStation "
                              f"Data Window export with {list(REQUIRED)}")
    if {"Up", "Down"} <= set(df.columns):
        volume = df["Up"].astype(float) + df["Down"].astype(float)
    elif "Vol" in df.columns:
        volume = df["Vol"].astype(float)
    else:
        volume = pd.Series(float("nan"), index=df.index)
    stamp = df["Date"].astype(str).str.strip() + " " + df["Time"].astype(str).str.strip()
    ts = pd.to_datetime(stamp, format="%m/%d/%Y %H:%M")
    out = pd.DataFrame({"open": df["Open"].astype(float).to_numpy(), "high": df["High"].astype(float).to_numpy(),
                        "low": df["Low"].astype(float).to_numpy(), "close": df["Close"].astype(float).to_numpy(),
                        "volume": volume.to_numpy()},
                       index=pd.DatetimeIndex(ts.to_numpy(), name="ts")).sort_index()
    if not out.index.is_unique:
        dup = [str(t) for t in out.index[out.index.duplicated()][:3]]
        raise BarsFormatError(f"duplicate bar timestamps, e.g. {dup}")
    if (out[["open", "high", "low", "close"]] <= 0).to_numpy().any():
        raise BarsFormatError("non-positive prices in bar file")
    if len(out) < 2:
        raise BarsFormatError("fewer than 2 bars")
    return out


def infer_interval(bars: pd.DataFrame) -> pd.Timedelta:
    """Most common spacing between consecutive bars (session gaps are the minority)."""
    diffs = bars.index.to_series().diff().dropna()
    return pd.Timedelta(diffs.mode().iloc[0])
