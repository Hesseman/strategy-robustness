import numpy as np
import pandas as pd
import pytest

from robustness.bars_loader import load_bars
from robustness.join import join_trades_to_bars, parse_interval_setting
from robustness.report_parser import parse_report
from conftest import make_bars, make_trades, bars_to_ts_text, trades_to_report_text


def _checks(res):
    return {c.name: c for c in res.checks}


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


def test_empty_trades_never_raises(mini_report_text, mini_bars_text):
    rep = parse_report(mini_report_text)
    res = join_trades_to_bars(rep.trades.iloc[0:0], load_bars(mini_bars_text))
    assert not res.ok
    assert res.checks[0].name == "has_trades" and not res.checks[0].passed and res.checks[0].severity == "error"
    assert list(res.trades.columns[-3:]) == ["entry_idx", "exit_idx", "hold_bars"] and len(res.trades) == 0
