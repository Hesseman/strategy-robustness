import numpy as np
import pandas as pd

from robustness.returns import forward_open_returns, matched_drift_baseline, pct_returns, usd_per_contract


def test_pct_and_usd_returns():
    t = pd.DataFrame({"direction": [1, -1], "entry_price": [100.0, 100.0], "exit_price": [110.0, 90.0],
                      "hold_bars": [3, 2], "contracts": [2, 3]})
    assert np.allclose(pct_returns(t), [0.10, 0.10])
    assert np.allclose(usd_per_contract(t, 2.0), [20.0, 20.0])   # fixed 1 contract, sizing ignored


def test_forward_open_returns():
    o = np.array([100.0, 110.0, 121.0, 133.1])
    assert np.allclose(forward_open_returns(o, 1), [0.1, 0.1, 0.1])
    assert np.allclose(forward_open_returns(o, 2), [0.21, 0.21])


def test_matched_baseline_is_exact_expectation():
    o = np.array([100.0, 102.0, 101.0, 105.0, 104.0, 108.0])
    holds = np.array([1, 2]); dirs = np.array([1, -1])
    b = matched_drift_baseline(o, holds, dirs)
    fwd1 = o[1:] / o[:-1] - 1            # 5 values
    fwd2 = o[2:] / o[:-2] - 1            # 4 values
    assert np.isclose(b.mean[0], fwd1.mean())
    assert np.isclose(b.mean[1], -fwd2.mean())
    assert np.isclose(b.win_rate[0], (fwd1 > 0).mean())
    assert np.isclose(b.win_rate[1], (fwd2 < 0).mean())


def test_matched_baseline_mask_restricts_entry_bars():
    o = np.array([100.0, 102.0, 101.0, 105.0, 104.0, 108.0])
    mask = np.array([True, True, False, False, False, False])
    b = matched_drift_baseline(o, np.array([1]), np.array([1]), mask=mask)
    fwd1 = o[1:] / o[:-1] - 1
    assert np.isclose(b.mean[0], fwd1[:2].mean())
