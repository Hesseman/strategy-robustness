"""Timing Sensitivity - Streamlit UI. Uploads -> parse -> join -> delayed-entry and
delayed-exit curves. A picture of fragility, not a gate: no verdict pill, no p-value."""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.copy import CARDS  # noqa: E402
from robustness import charts  # noqa: E402
from robustness.bars_loader import BarsFormatError, load_bars  # noqa: E402
from robustness.battery import ValidationFailed  # noqa: E402
from robustness.report_parser import ReportFormatError, parse_report  # noqa: E402
from robustness.timing import DelayCurve, run_timing, to_json  # noqa: E402

st.set_page_config(page_title="Timing Sensitivity", layout="wide")

MODE_LABELS = {"fixed_exit": "Fixed exit - a delayed entry keeps the reported exit",
               "fixed_hold": "Fixed hold - a delayed entry moves the exit too"}


def _esc(s: str) -> str:
    """Escape '$' so st.markdown does not read a pair of dollar amounts as LaTeX."""
    return s.replace("$", chr(92) + "$")


def _usd(v: float) -> str:
    return f"-${-v:,.0f}" if v < 0 else f"${v:,.0f}"


def _interval_label(value: str) -> str:
    """Accepts the str(Timedelta) run_timing stores (e.g. '0 days 00:30:00'); returns '30 min',
    '1 h', '1 day' or the input unchanged when it does not parse. Guarantees no exception."""
    try:
        td = pd.Timedelta(value)
    except Exception:
        return value
    minutes = int(td.total_seconds() // 60)
    if minutes % 1440 == 0:
        return f"{minutes // 1440} day" + ("s" if minutes // 1440 != 1 else "")
    if minutes % 60 == 0:
        return f"{minutes // 60} h"
    return f"{minutes} min"


@st.cache_data(show_spinner=False)
def _parse(report_bytes: bytes):
    return parse_report(report_bytes.decode("utf-8-sig", errors="replace"))


@st.cache_data(show_spinner=False)
def _bars(bars_bytes: bytes):
    return load_bars(bars_bytes.decode("utf-8-sig", errors="replace"))


@st.cache_data(show_spinner=False)
def demo_files() -> tuple[bytes, bytes]:
    """Synthetic report + bars (planted edge, seeds 30/31) for the demo button - the same
    demo the robustness app uses."""
    from robustness.synthetic import bars_to_ts_text, make_bars, make_trades, trades_to_report_text
    bars = make_bars(n=4000, seed=30)
    trades = make_trades(bars, n=80, seed=31, planted_edge=True)
    return trades_to_report_text(trades).encode("utf-8"), bars_to_ts_text(bars).encode("utf-8")


@st.cache_data(show_spinner="Computing the delay curves...")
def _timing(report_bytes: bytes, bars_bytes: bytes, max_k: int, mode: str):
    return run_timing(_parse(report_bytes), _bars(bars_bytes), max_k=max_k, mode=mode)


def result_lines(c: DelayCurve, n_trades: int) -> list[str]:
    """Accepts a DelayCurve and the trade count; returns the card's result bullets: what the
    first delay keeps (or changes, when there is no positive baseline), where the profit turns
    non-positive, and how many trades are still alive at the largest delay."""
    leg = "entry" if c.kind == "entry" else "exit"
    p0, p1, pk = c.points[0], c.points[1], c.points[-1]
    lines = [f"as reported (k = 0): **{_usd(p0.total_usd)}** gross over {p0.n_alive} trades, "
             f"mean {p0.mean_pct*100:+.3f}% per trade, win rate {p0.win_rate:.0%}"]
    if p1.n_alive == 0:
        lines.append(f"delaying {leg} 1 bar leaves no trade alive")
    elif math.isfinite(p1.retention):
        lines.append(f"delaying {leg} 1 bar keeps **{p1.retention:.0%}** of the gross $ "
                     f"({_usd(p1.total_usd)} of {_usd(p0.total_usd)}; {p1.n_alive} trades alive)")
    else:
        lines.append(f"delaying {leg} 1 bar changes the gross $ by **{_usd(p1.total_usd - p0.total_usd)}** "
                     f"({_usd(p0.total_usd)} → {_usd(p1.total_usd)}; no ratio - the as-reported total is not positive)")
    alive_ks = [p.k for p in c.points if p.n_alive > 0]
    if p0.total_usd <= 0:
        lines.append("not profitable as reported, so there is no profit for a delay to lose")
    elif c.first_nonpositive_k is not None:
        lines.append(f"profit turns non-positive at **k = {c.first_nonpositive_k}**")
    else:
        last = alive_ks[-1]
        lines.append(f"stays positive through **k = {last}**"
                     + (f" (no trade alive beyond k = {last})" if last < pk.k else ""))
    lines.append(f"n alive at k = {pk.k}: **{pk.n_alive} of {n_trades}**")
    return lines


def timing_card(key: str, c: DelayCurve, n_trades: int, fig: go.Figure) -> None:
    """Accepts a key from CARDS, its DelayCurve, the trade count and the plotly figure;
    renders one bordered card (copy and result lines left, chart right). No verdict pill."""
    cp = CARDS[key]
    with st.container(border=True):
        st.markdown(f"### {cp['title']}")
        st.caption(cp["tagline"])
        left, right = st.columns([1, 1.2])
        with left:
            st.markdown(_esc(f"**What it shows.** {cp['catches']}"))
            st.markdown(_esc(f"**How it works.** {cp['how']}"))
            st.markdown("**Result**")
            for line in result_lines(c, n_trades):
                st.markdown(_esc(f"- {line}"))
        with right:
            st.plotly_chart(fig, width="stretch")


st.title("Timing Sensitivity")
st.write("Upload a TradeStation **Strategy Performance Report** (saved as CSV) and the **bar data** it ran on "
         "(Data Window export, same symbol and interval). How much of the return survives when the entry, "
         "or the exit, is acted on 1, 2, ... bars late? Nothing is stored.")

with st.sidebar:
    st.header("Inputs")
    up_report = st.file_uploader("Performance report (.csv)", type=["csv", "txt"])
    up_bars = st.file_uploader("Bar data (.txt / .csv)", type=["txt", "csv"])
    max_k = st.slider("Largest delay, bars", min_value=1, max_value=20, value=10, step=1)
    mode = st.radio("Delayed entry", options=list(MODE_LABELS), format_func=MODE_LABELS.get, index=0)
    sample_report, sample_bars = os.environ.get("SR_SAMPLE_REPORT"), os.environ.get("SR_SAMPLE_BARS")
    use_sample = False
    if sample_report and sample_bars and Path(sample_report).exists() and Path(sample_bars).exists():
        use_sample = st.button("Load sample files (dev)")
        if use_sample:
            st.session_state["sample"] = True
    if st.button("Try the demo (synthetic strategy)"):
        st.session_state["demo"] = True
    if st.session_state.get("demo") or st.session_state.get("sample"):
        if st.button("Clear loaded data"):
            st.session_state.pop("demo", None); st.session_state.pop("sample", None); st.rerun()
    if st.session_state.get("demo"):
        report_bytes, bars_bytes = demo_files()
        st.caption("synthetic demo - a planted timing edge on random-walk bars, not a real strategy")
    elif st.session_state.get("sample"):
        report_bytes, bars_bytes = Path(sample_report).read_bytes(), Path(sample_bars).read_bytes()
        st.caption(f"sample: {Path(sample_report).name} + {Path(sample_bars).name}")
    else:
        report_bytes = up_report.getvalue() if up_report else None
        bars_bytes = up_bars.getvalue() if up_bars else None

if not (report_bytes and bars_bytes):
    st.info("Upload both files to start.")
    st.stop()

try:
    result = _timing(report_bytes, bars_bytes, int(max_k), str(mode))
except ReportFormatError as e:
    st.error(f"Report not readable: {e}"); st.stop()
except BarsFormatError as e:
    st.error(f"Bar file not readable: {e}"); st.stop()
except ValidationFailed as e:
    st.error("The report and the bars do not join - fix the inputs before the curves can be computed.")
    st.table([{"check": c.name, "ok": "✓" if c.passed else "✗", "detail": c.detail} for c in e.checks])
    st.stop()
except Exception as e:
    st.error("Could not process these files - check that the report is the CSV Strategy Performance "
             "Report and the bars are a Data Window export of the same symbol and interval. Details: "
             + f"{type(e).__name__}: {e}")
    st.stop()

m = result.meta
strip = st.columns(5)
for col, (label, value) in zip(strip, [
        ("Symbol", m["symbol"] or "-"), ("Interval", m["interval"] or "-"),
        ("Trades", f"{m['n_trades']} ({m['n_long']} L / {m['n_short']} S)"),
        ("Point value (USD / pt, inferred)", f"{m['point_value']:g}"),
        ("Bars", f"{m['n_bars']:,} at {_interval_label(m['bar_interval'])}")]):
    col.metric(label, value)
st.caption(f"{m['first_entry']:%Y-%m-%d} → {m['last_exit']:%Y-%m-%d} · delays 0..{m['max_k']} bars · "
           f"mode: {MODE_LABELS[m['mode']].lower()}")
for w in m["warnings"]:
    st.warning(w)

st.markdown(_esc(result.caveat))
st.markdown(_esc(f"**{result.at_open_share:.0%} of entries were filled at the bar open.** "
                 + ("The 0 → 1 step is a pure timing effect." if result.at_open_share >= 0.95 else
                    "The rest are stop/limit fills inside the bar, so the 0 → 1 step mixes a fill-price "
                    "effect (report price → next bar's open) with the timing effect.")))
with st.expander("Validation checks", expanded=not all(c.passed for c in result.checks)):
    st.table([{"check": c.name, "ok": "✓" if c.passed else ("⚠" if c.severity == "warn" else "✗"),
               "detail": c.detail} for c in result.checks])

pv_label = f"1 contract at {m['point_value']:g} USD/pt, gross"
timing_card("timing_entry", result.entry, m["n_trades"], charts.fig_delay_curve(result.entry, pv_label))
timing_card("timing_exit", result.exit, m["n_trades"], charts.fig_delay_curve(result.exit, pv_label))

st.download_button("Download results (JSON)", data=to_json(result), file_name="timing_results.json", mime="application/json")
