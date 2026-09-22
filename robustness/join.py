"""Join the report's trades to the bar series and validate the pair.

Only reason to change: the join contract (exact timestamp match on the workspace clock,
fill = bar open or inside the bar) or a validation rule. Each check is a named Check the
UI lists; 'error' checks block the battery, 'warn' checks do not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from robustness.bars_loader import infer_interval

_PRICE_TOL = 1e-6
_MONEY_TOL = 0.011


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    severity: str = "error"  # "error" blocks the battery, "warn" does not


@dataclass
class JoinResult:
    """trades: the report trades plus int columns entry_idx, exit_idx, hold_bars;
    point_value: dollars per 1.0 price point per contract, inferred from the report;
    cost_basis: 'per_trade' | 'per_contract' | 'unknown' - how TradeStation applied the
    report's commission/slippage; checks: every validation performed."""
    trades: pd.DataFrame
    point_value: float
    cost_basis: str
    checks: list[Check]

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")


def parse_interval_setting(s: str | None) -> pd.Timedelta | None:
    """'30 min.' -> 30 minutes; 'Daily' -> 1 day; 'Weekly' -> 7 days; tick/volume bars -> None."""
    if not s:
        return None
    t = s.strip().lower()
    m = re.match(r"^(\d+)\s*min", t)
    if m:
        return pd.Timedelta(minutes=int(m.group(1)))
    m = re.match(r"^(\d+)\s*hour", t)
    if m:
        return pd.Timedelta(hours=int(m.group(1)))
    if t.startswith("daily"):
        return pd.Timedelta(days=1)
    if t.startswith("weekly"):
        return pd.Timedelta(days=7)
    return None


def join_trades_to_bars(trades: pd.DataFrame, bars: pd.DataFrame, summary: dict | None = None,
                        settings: dict | None = None, min_trades: int = 30) -> JoinResult:
    """Locate every trade's entry and exit bar and run the validation checks. Returns a
    JoinResult; when timestamps are missing the index columns hold -1 and .ok is False.
    Never raises on bad data - the checks carry the diagnosis; an empty trade list returns
    a single failed `has_trades` check."""
    summary = summary or {}
    settings = settings or {}
    t = trades.copy()
    checks: list[Check] = []
    n = len(bars)

    if len(t) == 0:
        for col in ("entry_idx", "exit_idx", "hold_bars"):
            t[col] = np.array([], dtype=int)
        return JoinResult(t, float("nan"), "unknown",
                          [Check("has_trades", False, "the report has no trades")])

    date_only = bool((t.entry_time.dt.normalize() == t.entry_time).all()
                     and (t.exit_time.dt.normalize() == t.exit_time).all()
                     and bars.index.normalize().is_unique)
    key = bars.index.normalize() if date_only else bars.index
    pos = pd.Series(np.arange(n), index=key)
    e_key = t.entry_time.dt.normalize() if date_only else t.entry_time
    x_key = t.exit_time.dt.normalize() if date_only else t.exit_time
    e_idx = pos.reindex(e_key.to_numpy()).to_numpy()
    x_idx = pos.reindex(x_key.to_numpy()).to_numpy()
    missing = np.isnan(e_idx) | np.isnan(x_idx)
    if missing.any():
        ids = t.trade_id[missing].astype(int).tolist()
        checks.append(Check("timestamps_found", False,
                            f"{int(missing.sum())} trade(s) have an entry/exit time not present in the bars "
                            f"(first: trade {ids[0]}). Bars cover {bars.index[0]} -> {bars.index[-1]}; "
                            f"trades span {t.entry_time.min()} -> {t.exit_time.max()}. Wrong interval, symbol or date range?"))
        t["entry_idx"] = np.where(np.isnan(e_idx), -1, e_idx).astype(int)
        t["exit_idx"] = np.where(np.isnan(x_idx), -1, x_idx).astype(int)
        t["hold_bars"] = np.maximum(t.exit_idx - t.entry_idx, 0)
        return JoinResult(t, float("nan"), "unknown", checks)
    checks.append(Check("timestamps_found", True, f"all {len(t)} trades' entry and exit times found in {n} bars"
                        + (" (joined on date)" if date_only else "")))
    t["entry_idx"] = e_idx.astype(int)
    t["exit_idx"] = x_idx.astype(int)
    t["hold_bars"] = (t.exit_idx - t.entry_idx).astype(int)
    if (t.hold_bars < 0).any():
        checks.append(Check("exit_after_entry", False, f"{int((t.hold_bars < 0).sum())} trade(s) exit before they enter"))
    else:
        checks.append(Check("exit_after_entry", True, "every exit is at or after its entry"))

    eb = bars.iloc[t.entry_idx.to_numpy()]
    xb = bars.iloc[t.exit_idx.to_numpy()]
    ep, xp = t.entry_price.to_numpy(), t.exit_price.to_numpy()
    in_e = (ep >= eb.low.to_numpy() - _PRICE_TOL) & (ep <= eb.high.to_numpy() + _PRICE_TOL)
    in_x = (xp >= xb.low.to_numpy() - _PRICE_TOL) & (xp <= xb.high.to_numpy() + _PRICE_TOL)
    bad = ~(in_e & in_x)
    at_open = float(np.mean(np.isclose(ep, eb.open.to_numpy())))
    checks.append(Check("prices_in_bar_range", bool(not bad.any()),
                        (f"{int(bad.sum())} fill(s) lie outside their bar's high-low range (first: trade "
                         f"{int(t.trade_id[bad].iloc[0])}) - are these bars for the same symbol?") if bad.any()
                        else f"all fills inside their bar's range; {at_open:.0%} of entries at the bar open"))

    pts = t.direction.to_numpy() * (xp - ep) * t.contracts.to_numpy()
    nz = pts != 0
    if nz.any():
        pv = t.gross_pnl.to_numpy()[nz] / pts[nz]
        pv_med = float(np.round(np.median(pv), 4))
        spread = float(np.max(np.abs(pv - pv_med)))
        checks.append(Check("point_value_constant", bool(spread < 0.005),
                            f"gross P&L / (direction x price change x contracts) = {pv_med} per point"
                            + ("" if spread < 0.005 else f", but varies by up to {spread:.4f} across trades")))
    else:
        pv_med = float("nan")
        checks.append(Check("point_value_constant", False, "no trade with a non-zero price change; cannot infer point value"))

    rt = 2 * (t.comm_side.to_numpy() + t.slip_side.to_numpy())
    err_trade = np.nanmax(np.abs(t.gross_pnl.to_numpy() - rt - t.net_pnl.to_numpy()))
    err_ctr = np.nanmax(np.abs(t.gross_pnl.to_numpy() - rt * t.contracts.to_numpy() - t.net_pnl.to_numpy()))
    if err_trade < _MONEY_TOL:
        basis = "per_trade"
    elif err_ctr < _MONEY_TOL:
        basis = "per_contract"
    else:
        basis = "unknown"
    checks.append(Check("net_reconciles", basis != "unknown",
                        f"net = gross - 2 x (commission + slippage) applied {basis.replace('_', ' ')}" if basis != "unknown"
                        else f"net P&L does not reconcile to gross minus the report's costs (max error {min(err_trade, err_ctr):.2f})",
                        severity="warn"))

    avg = summary.get("Avg. Bars in Total Trades")
    if isinstance(avg, (int, float)) and not np.isnan(avg):
        ours = float(t.hold_bars.mean() + 1.0)
        checks.append(Check("hold_matches_summary", abs(ours - avg) <= 0.05,
                            f"mean bars per trade {ours:.2f} (inclusive) vs report {avg:.2f}", severity="warn"))
    else:
        checks.append(Check("hold_matches_summary", True, "report summary has no 'Avg. Bars in Total Trades' to compare", severity="warn"))

    want = parse_interval_setting(settings.get("interval"))
    have = infer_interval(bars)
    if want is None:
        checks.append(Check("interval_matches_bars", True, f"report interval {settings.get('interval')!r} not time-based or absent; bars step {have}", severity="warn"))
    else:
        checks.append(Check("interval_matches_bars", want == have, f"report interval {settings.get('interval')!r} vs bar spacing {have}"))

    checks.append(Check("min_trades", len(t) >= min_trades,
                        f"{len(t)} trades" + ("" if len(t) >= min_trades else f" (< {min_trades}: gates are not applied)"), severity="warn"))
    return JoinResult(t, pv_med, basis, checks)
