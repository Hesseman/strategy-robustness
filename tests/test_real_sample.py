"""Oracle test on the user's real MNQ 30-min sample. Skipped when the files are absent.
Never copy these files into the repo."""
import os
from pathlib import Path

import pytest

from robustness.bars_loader import load_bars
from robustness.join import join_trades_to_bars
from robustness.report_parser import parse_report

REPORT = Path(os.environ.get("SR_SAMPLE_REPORT", "C:/Users/User/Downloads/MNQ30MDSP.csv"))
BARS = Path(os.environ.get("SR_SAMPLE_BARS", "C:/Users/User/Downloads/MNQ30M_BarData_Tradestation.txt"))

pytestmark = pytest.mark.skipif(not (REPORT.exists() and BARS.exists()), reason="real sample files not present")


def test_real_sample_parses_and_joins():
    rep = parse_report(REPORT.read_text(encoding="utf-8-sig"))
    bars = load_bars(BARS.read_text(encoding="utf-8-sig"))
    assert len(rep.trades) == 418
    assert rep.settings["symbol"] == "@MNQ" and rep.settings["interval"] == "30 min."
    assert rep.summary["Total Number of Trades"] == 418
    res = join_trades_to_bars(rep.trades, bars, summary=rep.summary, settings=rep.settings)
    assert res.ok and all(c.passed for c in res.checks), [c for c in res.checks if not c.passed]
    assert res.point_value == 2.0
    assert res.cost_basis == "per_trade"
    assert abs(res.trades.hold_bars.mean() + 1 - 41.22) < 0.01
