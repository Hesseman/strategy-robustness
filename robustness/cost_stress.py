"""T7 - cost sensitivity as an assumption haircut, not execution realism (spec decision 7).
Every trade's 1-contract gross $ is reduced by k x the reference round-trip cost; the gate
is the net lift over the matched drift baseline at k = 1. Breakeven multiplier = how many
times the assumed cost the edge could absorb."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class CostStressResult:
    cost_rt_usd: float
    cost_source: str            # "multiwalk" (reference table) | "report" (fallback: the report's own costs)
    ts_cost_rt_usd: float | None
    gross_mean_usd: float
    baseline_mean_usd: float
    mults: list[float]
    net_mean_usd: list[float]
    net_lift_usd: list[float]
    passes: list[bool]
    breakeven_mult: float
    passed_1x: bool
    net_pf_1x: float


def cost_stress(usd_pc: np.ndarray, baseline_usd: np.ndarray, cost_rt_usd: float, cost_source: str,
                ts_cost_rt_usd: float | None = None,
                mults: tuple[float, ...] = (0, 1, 2, 3, 5, 10, 20)) -> CostStressResult:
    """usd_pc: gross $ per trade for 1 contract; baseline_usd: matched drift per trade in $;
    cost_rt_usd: reference round trip per contract. Guarantees passes[i] == (net_lift_usd[i] > 0)."""
    usd_pc = np.asarray(usd_pc, dtype=float); baseline_usd = np.asarray(baseline_usd, dtype=float)
    g = float(usd_pc.mean()); b = float(np.nanmean(baseline_usd))
    net_mean = [g - k * cost_rt_usd for k in mults]
    net_lift = [m - b for m in net_mean]
    passes = [bool(x > 0) for x in net_lift]
    breakeven = (g - b) / cost_rt_usd if cost_rt_usd > 0 else float("inf")
    net1 = usd_pc - cost_rt_usd
    losses = -net1[net1 < 0].sum()
    pf = float(net1[net1 > 0].sum() / losses) if losses > 0 else float("inf")
    return CostStressResult(cost_rt_usd=cost_rt_usd, cost_source=cost_source, ts_cost_rt_usd=ts_cost_rt_usd,
                            gross_mean_usd=g, baseline_mean_usd=b, mults=list(mults), net_mean_usd=net_mean,
                            net_lift_usd=net_lift, passes=passes, breakeven_mult=float(breakeven),
                            passed_1x=passes[list(mults).index(1)] if 1 in mults else bool((g - cost_rt_usd - b) > 0),
                            net_pf_1x=pf)
