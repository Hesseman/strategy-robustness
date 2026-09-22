import numpy as np
import pytest

from robustness.cost_stress import cost_stress


def test_cost_stress_arithmetic():
    usd = np.array([50.0, -20.0, 30.0, 10.0])          # mean 17.5
    base = np.array([2.0, 2.0, 2.0, 2.0])               # mean 2.0
    r = cost_stress(usd, base, cost_rt_usd=5.74, cost_source="multiwalk", ts_cost_rt_usd=5.40)
    assert r.mults == [0, 1, 2, 3, 5, 10, 20]
    assert np.isclose(r.gross_mean_usd, 17.5) and np.isclose(r.baseline_mean_usd, 2.0)
    assert np.isclose(r.net_lift_usd[1], 17.5 - 5.74 - 2.0)
    assert r.passes[1] is True and r.passes[3] is False    # 3x: 17.5 - 17.22 - 2 < 0
    assert np.isclose(r.breakeven_mult, 15.5 / 5.74)
    assert r.passed_1x is True
    net1 = usd - 5.74
    assert np.isclose(r.net_pf_1x, net1[net1 > 0].sum() / -net1[net1 < 0].sum())
    assert r.cost_source == "multiwalk" and r.ts_cost_rt_usd == 5.40


def test_zero_cost_gives_infinite_breakeven():
    r = cost_stress(np.array([1.0, 2.0]), np.array([0.0, 0.0]), cost_rt_usd=0.0, cost_source="report")
    assert r.breakeven_mult == float("inf") and r.passed_1x is True


def test_negative_lift_fails_even_at_zero_cost():
    r = cost_stress(np.array([1.0, 1.0]), np.array([3.0, 3.0]), cost_rt_usd=1.0, cost_source="multiwalk")
    assert r.passes[0] is False and r.passed_1x is False and r.breakeven_mult < 0
