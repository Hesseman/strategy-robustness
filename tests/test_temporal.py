import numpy as np
import pandas as pd

from robustness.returns import pct_returns, usd_per_contract
from robustness.temporal import temporal_test
from conftest import make_bars, make_trades


def _run(n_trades=80, seed=21, **kw):
    bars = make_bars(n=4000, seed=20)
    t = make_trades(bars, n=n_trades, seed=seed)
    t["hold_bars"] = t.exit_idx - t.entry_idx
    return bars, t, temporal_test(bars, t.entry_idx.to_numpy(), t.hold_bars.to_numpy(), t.direction.to_numpy(),
                                  pct_returns(t), usd_per_contract(t, 2.0), pd.DatetimeIndex(t.exit_time), **kw)


def test_windows_partition_the_trades():
    bars, t, res = _run()
    assert len(res.windows) == 4
    assert sum(w.n for w in res.windows) == len(t)
    assert res.windows[0].start == bars.index[0] and res.windows[-1].end == bars.index[-1]
    assert res.windows_total == sum(1 for w in res.windows if w.counted)
    assert 0.0 <= res.score <= 1.0
    for w in res.windows:
        if w.counted:
            assert np.isclose(w.lift, w.mean - w.baseline)


def test_small_windows_are_not_counted():
    _, t, res = _run(n_trades=12, seed=22, min_n=10)
    assert res.windows_total < 4 or all(w.n >= 10 for w in res.windows)


def test_crisis_split_covers_all_trades():
    bars, t, res = _run()
    c = res.crisis
    assert c["n_crisis"] + c["n_calm"] == len(t)
    assert 0.08 <= c["n_crisis_bars"] / len(bars) <= 0.12       # top decile of vol bars
    if c["n_crisis"] >= 10:
        assert np.isclose(c["lift_crisis"], c["mean_crisis"] - c["baseline_crisis"])


def test_yearly_table_sums_to_total():
    _, t, res = _run()
    usd = usd_per_contract(t, 2.0)
    assert np.isclose(res.yearly.usd.sum(), usd.sum())
    assert res.yearly.n.sum() == len(t)
    assert res.years_total == len(res.yearly) and res.years_positive == int((res.yearly.usd > 0).sum())


def test_membership_is_by_entry_bar_and_nan_vol_is_never_crisis():
    bars = make_bars(n=400, seed=23)
    entry_idx = np.array([0, 50, 90, 150, 250, 350])
    holds = np.array([5, 100, 20, 5, 5, 5])          # the bar-50 trade exits inside window 1 (bar 150)
    directions = np.array([1, 1, -1, 1, -1, 1])
    open_ = bars.open.to_numpy()
    pct = directions * (open_[entry_idx + holds] / open_[entry_idx] - 1)
    usd = directions * (open_[entry_idx + holds] - open_[entry_idx]) * 2.0
    exit_times = pd.DatetimeIndex(bars.index[entry_idx + holds])
    res = temporal_test(bars, entry_idx, holds, directions, pct, usd, exit_times, min_n=1)
    assert [w.n for w in res.windows] == [3, 1, 1, 1]        # bars 0-99 | 100-199 | 200-299 | 300-399, by ENTRY bar
    assert res.windows[0].end == bars.index[99] and res.windows[1].start == bars.index[100]
    vol = pd.Series(bars.close.to_numpy()).pct_change().rolling(20, min_periods=1).std().to_numpy()
    independent_crisis = vol >= np.nanquantile(vol, 0.9)       # NaN compares False: an independent formulation
    assert np.isnan(vol[0]) and not independent_crisis[0]
    assert res.crisis["n_crisis"] == int(independent_crisis[entry_idx].sum())
    assert res.crisis["n_calm"] == len(entry_idx) - res.crisis["n_crisis"]
