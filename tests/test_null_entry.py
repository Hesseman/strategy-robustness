import numpy as np
import pytest

from robustness.null_entry import random_entry_test
from robustness.returns import matched_drift_baseline, pct_returns
from conftest import make_bars, make_trades


def _setup(planted_edge, seed_bars=11, seed_trades=12, n=80):
    bars = make_bars(n=4000, seed=seed_bars)
    trades = make_trades(bars, n=n, seed=seed_trades, planted_edge=planted_edge)
    trades["hold_bars"] = trades.exit_idx - trades.entry_idx
    open_ = bars.open.to_numpy()
    return open_, trades


def test_null_centre_equals_matched_baseline():
    open_, t = _setup(planted_edge=False)
    res = random_entry_test(open_, t.hold_bars.to_numpy(), t.direction.to_numpy(), pct_returns(t), n_perm=2000, seed=0)
    base = matched_drift_baseline(open_, t.hold_bars.to_numpy(), t.direction.to_numpy())
    assert np.isclose(res.baseline_mean, base.mean.mean())
    assert abs(res.null_mean - res.baseline_mean) < 4 * res.null_std / np.sqrt(res.n_perm)
    assert res.null.shape == (2000,) and res.n_perm == 2000


def test_random_strategy_is_not_significant():
    open_, t = _setup(planted_edge=False)
    res = random_entry_test(open_, t.hold_bars.to_numpy(), t.direction.to_numpy(), pct_returns(t), n_perm=1000, seed=0)
    assert abs(res.z) < 3.5
    assert res.p_value == (res.k_ge + 1) / (res.n_perm + 1)


def test_p_value_counts_the_observed_as_a_draw_so_it_is_never_zero():
    open_, t = _setup(planted_edge=False)
    unbeatable = np.full(len(t), 1.0)  # +100% per trade: no random set can match it
    res = random_entry_test(open_, t.hold_bars.to_numpy(), t.direction.to_numpy(), unbeatable, n_perm=100, seed=0)
    assert res.k_ge == 0
    assert res.p_value == 1 / 101 and res.p_value > 0


def test_planted_edge_is_significant():
    open_, t = _setup(planted_edge=True)
    res = random_entry_test(open_, t.hold_bars.to_numpy(), t.direction.to_numpy(), pct_returns(t), n_perm=1000, seed=0)
    assert res.p_value < 0.01 and res.lift > 0 and res.z > 3


def test_deterministic_with_seed():
    open_, t = _setup(planted_edge=False)
    a = random_entry_test(open_, t.hold_bars.to_numpy(), t.direction.to_numpy(), pct_returns(t), n_perm=300, seed=5)
    b = random_entry_test(open_, t.hold_bars.to_numpy(), t.direction.to_numpy(), pct_returns(t), n_perm=300, seed=5)
    assert np.array_equal(a.null, b.null)


def test_hold_outside_series_raises():
    open_ = np.linspace(100.0, 110.0, 50)
    with pytest.raises(ValueError, match="every hold must be"):
        random_entry_test(open_, np.array([0]), np.array([1]), np.array([0.01]), n_perm=10)
    with pytest.raises(ValueError, match="every hold must be"):
        random_entry_test(open_, np.array([50]), np.array([1]), np.array([0.01]), n_perm=10)
    res = random_entry_test(open_, np.array([49]), np.array([1]), np.array([0.01]), n_perm=10)  # boundary hold accepted
    assert res.n_trades == 1 and res.n_perm == 10
