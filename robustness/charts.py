"""Plotly figures for the five cards. No Streamlit here."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from robustness.cost_stress import CostStressResult
from robustness.drawdown import DrawdownResult
from robustness.null_entry import RandomEntryResult
from robustness.temporal import TemporalResult

ACCENT, MUTED, GREEN, RED, PALE = "#1f5fbf", "#9a9a94", "#2e8b57", "#c0392b", "#dfe7f5"
_LAYOUT = dict(template="plotly_white", margin=dict(l=40, r=20, t=20, b=40), height=320, showlegend=False)


def fig_baseline(r: RandomEntryResult) -> go.Figure:
    """Bar chart: strategy mean return vs the matched random-entry baseline, % of price."""
    fig = go.Figure(go.Bar(x=["strategy", "random entry, same holds"], y=[r.observed_mean * 100, r.baseline_mean * 100],
                           marker_color=[ACCENT, MUTED], text=[f"{r.observed_mean*100:+.3f}%", f"{r.baseline_mean*100:+.3f}%"],
                           textposition="outside"))
    fig.update_layout(**_LAYOUT, yaxis_title="mean return per trade, % of price (1 contract)")
    return fig


def fig_null_hist(r: RandomEntryResult) -> go.Figure:
    """Histogram of the T8a random-entry null distribution with the observed mean marked."""
    fig = go.Figure(go.Histogram(x=r.null * 100, nbinsx=40, marker_color=MUTED, name="random-entry sets"))
    fig.add_vline(x=r.observed_mean * 100, line_color=ACCENT, line_width=3,
                  annotation_text=f"strategy {r.observed_mean*100:+.3f}%", annotation_position="top")
    fig.update_layout(**_LAYOUT, xaxis_title=f"mean return of {r.n_trades} random entries with the strategy's holds, %",
                      yaxis_title=f"count of {r.n_perm} random sets")
    return fig


def fig_windows(t3: TemporalResult) -> go.Figure:
    """Bar chart of T3's four equal-bar-count windows, lift vs drift per window."""
    xs = [f"{w.start:%Y-%m}→{w.end:%Y-%m}" for w in t3.windows]
    lifts = [(w.lift or 0.0) * 100 for w in t3.windows]
    cols = [GREEN if (w.counted and w.lift is not None and w.lift > 0) else (RED if w.counted else MUTED) for w in t3.windows]
    fig = go.Figure(go.Bar(x=xs, y=lifts, marker_color=cols, text=[f"n={w.n}" for w in t3.windows], textposition="outside"))
    fig.add_hline(y=0, line_color=MUTED)
    fig.update_layout(**_LAYOUT, yaxis_title="lift vs drift, % per trade", xaxis_title="window (equal bar counts)")
    return fig


def fig_yearly(t3: TemporalResult) -> go.Figure:
    """Bar chart of $ P&L per calendar year of exit, 1 contract, gross."""
    y = t3.yearly
    fig = go.Figure(go.Bar(x=y.year.astype(str), y=y.usd, marker_color=[GREEN if v > 0 else RED for v in y.usd],
                           text=[f"n={n}" for n in y.n], textposition="outside"))
    fig.update_layout(**_LAYOUT, yaxis_title="$ per year, 1 contract, gross", xaxis_title="calendar year of exit")
    return fig


def fig_cost_curve(t7: CostStressResult) -> go.Figure:
    """Net lift vs drift as a function of the cost multiplier, with the break-even marked."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t7.mults, y=t7.net_lift_usd, mode="lines+markers", line_color=ACCENT, fill="tozeroy", fillcolor=PALE))
    fig.add_hline(y=0, line_color=RED, line_dash="dash")
    if np.isfinite(t7.breakeven_mult) and t7.breakeven_mult > 0:
        fig.add_vline(x=t7.breakeven_mult, line_color=MUTED, line_dash="dot", annotation_text=f"break-even {t7.breakeven_mult:.1f}x")
    fig.update_layout(**_LAYOUT, xaxis_title=f"cost multiplier (1x = ${t7.cost_rt_usd:.2f} round trip per contract)",
                      yaxis_title="net lift vs drift, $ per trade (1 contract)")
    return fig


def fig_equity(dd: DrawdownResult) -> go.Figure:
    """Cumulative $ P&L equity curve, 1 contract, with drawdown episodes shaded."""
    fig = go.Figure(go.Scatter(x=dd.times, y=dd.equity, mode="lines", line_color=ACCENT, name="equity"))
    for e in dd.episodes:
        end_i = e["recovery_i"] if e["recovery_i"] is not None else len(dd.times) - 1
        fig.add_vrect(x0=dd.times[e["peak_i"]], x1=dd.times[end_i], fillcolor=RED, opacity=0.08, line_width=0)
    fig.update_layout(**_LAYOUT, yaxis_title="cumulative $ P&L, 1 contract, gross", xaxis_title="trade close")
    return fig


def fig_episode_hist(dd: DrawdownResult) -> go.Figure:
    """Histogram of drawdown episode depths with CDaR-80 and the max drawdown marked."""
    fig = go.Figure(go.Histogram(x=dd.depths, nbinsx=30, marker_color=MUTED))
    fig.add_vline(x=dd.cdar80, line_color=ACCENT, line_width=3, annotation_text=f"CDaR-80 ${dd.cdar80:,.0f}", annotation_position="top")
    fig.add_vline(x=dd.max_dd, line_color=RED, line_dash="dash", annotation_text=f"max ${dd.max_dd:,.0f}", annotation_position="bottom right")
    fig.update_layout(**_LAYOUT, xaxis_title="drawdown episode depth, $", yaxis_title="episodes")
    return fig
