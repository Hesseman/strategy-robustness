import numpy as np
import pandas as pd
import pytest

from robustness.bars_loader import load_bars
from robustness.join import join_trades_to_bars, parse_interval_setting
from robustness.report_parser import parse_report
from conftest import make_bars, make_trades, bars_to_ts_text, trades_to_report_text


def _checks(res):
    return {c.name: c for c in res.checks}


def _ty_like_bars(n_bars: int = 400, seed: int = 30, p0: float = 110.0) -> pd.DataFrame:
    """Synthetic bars with prices on exact 1/64 ticks (TY/FV/TU-style quoting).
    Built directly rather than through make_bars + bars_to_ts_text, whose $.2f
    price-cell formatting would round away the sub-cent tick fractions this
    fixture needs - the point-value check reads entry/exit prices straight off
    the trades frame, so precision there is what the test is exercising."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, 0.001, n_bars)
    close = p0 * np.cumprod(1.0 + rets)
    open_ = np.concatenate([[p0], close[:-1]])
    open_64 = np.round(open_ * 64) / 64
    close_64 = np.round(close * 64) / 64
    hi = np.maximum(open_64, close_64) + 2 / 64
    lo = np.minimum(open_64, close_64) - 2 / 64
    idx = pd.date_range("2024-01-02 08:30", periods=n_bars, freq="30min", name="ts")
    return pd.DataFrame({"open": open_64, "high": hi, "low": lo, "close": close_64,
                         "volume": np.full(n_bars, 100.0)}, index=idx)


def test_mini_join(mini_report_text, mini_bars_text):
    rep = parse_report(mini_report_text)
    bars = load_bars(mini_bars_text)
    res = join_trades_to_bars(rep.trades, bars, summary=rep.summary, settings=rep.settings, min_trades=30)
    t = res.trades
    assert t.entry_idx.tolist() == [1, 9] and t.exit_idx.tolist() == [6, 15]
    assert t.hold_bars.tolist() == [5, 6]
    assert res.point_value == 2.0
    assert res.cost_basis == "per_trade"
    c = _checks(res)
    assert c["timestamps_found"].passed
    assert c["prices_in_bar_range"].passed
    assert c["point_value_constant"].passed
    assert c["net_reconciles"].passed
    assert c["hold_matches_summary"].passed          # mean(5,6)+1 == 6.50
    assert c["interval_matches_bars"].passed
    assert not c["min_trades"].passed and c["min_trades"].severity == "warn"
    assert res.ok                                    # warn checks do not block


def test_missing_timestamp_fails(mini_report_text, mini_bars_text):
    rep = parse_report(mini_report_text)
    bars = load_bars(mini_bars_text).drop(pd.Timestamp("2025-01-06 11:30"))
    res = join_trades_to_bars(rep.trades, bars)
    c = _checks(res)
    assert not c["timestamps_found"].passed and "trade 1" in c["timestamps_found"].detail
    assert not res.ok


def test_wrong_symbol_prices_fail(mini_report_text, mini_bars_text):
    rep = parse_report(mini_report_text)
    bars = load_bars(mini_bars_text)
    bars[["open", "high", "low", "close"]] *= 0.25      # ES-sized prices for an MNQ report
    res = join_trades_to_bars(rep.trades, bars)
    assert not _checks(res)["prices_in_bar_range"].passed and not res.ok


def test_interval_mismatch_fails(mini_report_text, mini_bars_text):
    rep = parse_report(mini_report_text)
    rep.settings["interval"] = "5 min."
    res = join_trades_to_bars(rep.trades, load_bars(mini_bars_text), settings=rep.settings)
    assert not _checks(res)["interval_matches_bars"].passed and not res.ok


def test_parse_interval_setting():
    assert parse_interval_setting("30 min.") == pd.Timedelta(minutes=30)
    assert parse_interval_setting("1 min.") == pd.Timedelta(minutes=1)
    assert parse_interval_setting("Daily") == pd.Timedelta(days=1)
    assert parse_interval_setting("500 Tick") is None
    assert parse_interval_setting(None) is None


def test_synthetic_join_passes_all_error_checks():
    bars = make_bars(n=3000, seed=8)
    trades = make_trades(bars, n=60, seed=9)
    rep = parse_report(trades_to_report_text(trades))
    res = join_trades_to_bars(rep.trades, load_bars(bars_to_ts_text(bars)), summary=rep.summary, settings=rep.settings)
    assert res.ok and all(c.passed for c in res.checks)
    assert res.trades.entry_idx.tolist() == trades.entry_idx.tolist()
    assert res.trades.hold_bars.tolist() == (trades.exit_idx - trades.entry_idx).tolist()


def test_point_value_check_judges_dollar_residual_not_pv_spread():
    """TY/FV/TU-style instrument: 1/64 ticks x $1000/point. Cent-rounded gross P&L
    makes the per-trade point-value estimate wobble in point-value units even
    though it reproduces the report's dollar P&L almost exactly - the check must
    judge the dollar residual, not the spread of pv_i = gross_pnl / points."""
    bars = _ty_like_bars(seed=30)
    trades = make_trades(bars, n=40, seed=31, point_value=1000.0)
    res = join_trades_to_bars(trades, bars)
    assert _checks(res)["point_value_constant"].passed
    assert abs(res.point_value - 1000.0) < 0.01


def test_empty_trades_never_raises(mini_report_text, mini_bars_text):
    rep = parse_report(mini_report_text)
    res = join_trades_to_bars(rep.trades.iloc[0:0], load_bars(mini_bars_text))
    assert not res.ok
    assert res.checks[0].name == "has_trades" and not res.checks[0].passed and res.checks[0].severity == "error"
    assert list(res.trades.columns[-3:]) == ["entry_idx", "exit_idx", "hold_bars"] and len(res.trades) == 0
