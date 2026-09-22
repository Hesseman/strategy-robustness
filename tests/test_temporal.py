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
