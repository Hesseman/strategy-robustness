"""Shared test fixtures: the hand-made mini TradeStation files and a synthetic
report/bar generator that writes the exact TradeStation layouts."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mini_report_text() -> str:
    return (FIXTURES / "mini_report.csv").read_bytes().decode("utf-8")


@pytest.fixture
def mini_bars_text() -> str:
    return (FIXTURES / "mini_bars.txt").read_bytes().decode("utf-8")


def make_bars(n: int = 3000, step_min: int = 30, seed: int = 1, p0: float = 20000.0,
              start: str = "2024-01-02 08:30") -> pd.DataFrame:
    """Random-walk bars with a regular step (no session gaps). Index name 'ts';
    columns open/high/low/close/volume; open[i] == close[i-1]."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, 0.002, n)
    close = p0 * np.cumprod(1.0 + rets)
    open_ = np.concatenate([[p0], close[:-1]])
    hi = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.0007, n)))
    lo = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.0007, n)))
    idx = pd.date_range(start, periods=n, freq=f"{step_min}min", name="ts")
    vol = rng.integers(50, 500, n).astype(float)
    return pd.DataFrame({"open": open_.round(2), "high": hi.round(2), "low": lo.round(2),
                         "close": close.round(2), "volume": vol}, index=idx)


def bars_to_ts_text(bars: pd.DataFrame) -> str:
    """Render bars in the TradeStation Data Window layout (quoted header, Up/Down, PLOT1)."""
    lines = ['"Date","Time","Open","High","Low","Close","Up","Down","PLOT1"']
    for ts, r in bars.iterrows():
        up = int(r.volume // 2); down = int(r.volume - up)
        lines.append(f"{ts:%m/%d/%Y},{ts:%H:%M},{r.open:.2f},{r.high:.2f},{r.low:.2f},{r.close:.2f},{up},{down},0.00")
    return "\n".join(lines) + "\n"


def make_trades(bars: pd.DataFrame, n: int = 60, seed: int = 2, point_value: float = 2.0,
                comm: float = 2.20, slip: float = 0.50, planted_edge: bool = False,
                max_hold: int = 40) -> pd.DataFrame:
    """Non-overlapping trades filled at bar opens. planted_edge=True exits each trade at
    the best open within its hold window (look-ahead) so the strategy beats random timing."""
    rng = np.random.default_rng(seed)
    n_bars = len(bars)
    open_ = bars["open"].to_numpy()
    starts = np.sort(rng.choice(np.arange(10, n_bars - max_hold - 2), size=n, replace=False))
    recs = []
    prev_exit = -1
    for k, e in enumerate(starts, start=1):
        e = max(int(e), prev_exit + 1)
        hold = int(rng.integers(1, max_hold + 1))
        x = min(e + hold, n_bars - 1)
        if x <= e:
            continue
        direction = int(rng.choice([1, -1]))
        if planted_edge:
            window = open_[e + 1: x + 1]
            best = int(np.argmax(window) if direction == 1 else np.argmin(window))
            x = e + 1 + best
        contracts = int(rng.choice([1, 2, 3]))
        ep, xp = float(open_[e]), float(open_[x])
        gross = direction * (xp - ep) * point_value * contracts
        recs.append({"trade_id": k, "direction": direction, "entry_idx": e, "exit_idx": x,
                     "entry_time": bars.index[e], "exit_time": bars.index[x],
                     "entry_price": ep, "exit_price": xp, "contracts": contracts,
                     "gross_pnl": round(gross, 2), "net_pnl": round(gross - 2 * (comm + slip), 2),
                     "comm_side": comm, "slip_side": slip})
        prev_exit = x
    return pd.DataFrame(recs)


def _money(v: float) -> str:
    return f"${v:.2f}" if v >= 0 else f"(${-v:.2f})"


def _ts(t: pd.Timestamp) -> str:
    return f"{t.month}/{t.day}/{t.year} {t:%H:%M}"


def trades_to_report_text(trades: pd.DataFrame, symbol: str = "@MNQ", interval: str = "30 min.") -> str:
    """Render trades in the TradeStation performance-report CSV layout (paired rows, CRLF)."""
    long = trades[trades.direction == 1]; short = trades[trades.direction == -1]
    avg_bars = float((trades.exit_idx - trades.entry_idx).mean() + 1.0)
    out = ["", "", "Performance Summary", "", ",,,,", "TradeStation Performance Summary,,,,", ",,,,",
           ",All Trades,Long Trades,Short Trades,",
           f"Total Net Profit,{_money(trades.net_pnl.sum())},{_money(long.net_pnl.sum())},{_money(short.net_pnl.sum())},",
           f"Total Number of Trades,{len(trades)},{len(long)},{len(short)},",
           f"Avg. Bars in Total Trades,{avg_bars:.2f},{avg_bars:.2f},{avg_bars:.2f},",
           "", "", "TradeStation Trades List", "",
           "#,Type,Date/Time,Signal,Price,Roll Over Pips,Shares/Ctrts - Profit/Loss,Net Profit - Cum Net Profit,% Profit,Run-up/Drawdown,Efficiency,Total Eff.,Comm.,Slippage",
           ""]
    cum = 0.0
    for r in trades.itertuples():
        cum += r.net_pnl
        etype, xtype = ("Buy", "Sell") if r.direction == 1 else ("Sell Short", "Buy to Cover")
        pct = r.direction * (r.exit_price / r.entry_price - 1) * 100
        out.append(f"{r.trade_id},{etype},{_ts(r.entry_time)},Entry,{_money(r.entry_price)},$0.00,{r.contracts},"
                   f"{_money(r.net_pnl)},{pct:.2f}%,$10.00,50.00%,,{_money(r.comm_side)},{_money(r.slip_side)}")
        out.append(f",{xtype},{_ts(r.exit_time)},Exit,{_money(r.exit_price)},,{_money(r.gross_pnl)},{_money(cum)},,"
                   f"($5.00),50.00%,10.00%,{_money(r.comm_side)},{_money(r.slip_side)}")
    out += ["", "Trade Analysis", "", ",,,,", "TradeStation Trade Analysis,,,,",
            f"Total Number of Trades,{len(trades)},0,0,", "", "Settings", "", ",,,",
            "TradeStation Chart Settings,,,", f"Symbol,{symbol},,", "Description,Synthetic,,",
            f"Interval,{interval},,", "Start Date/Time,1/2/2024 8:30:00 AM,,", "End Date/Time,1/1/2025 4:00:00 PM,,",
            ",,,", "TradeStation Strategies Applied,,,", "Synthetic_Strategy(On),,,", ",,,",
            "TradeStation Strategy Settings,,,", "Synthetic_Strategy - Length,20,,", "Trade Size,,,",
            "Fixed Shares/Contracts:,1,,", ""]
    return "\r\n".join(out)
