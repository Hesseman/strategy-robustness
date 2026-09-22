"""Shared test fixtures: the hand-made mini TradeStation files and a synthetic
report/bar generator that writes the exact TradeStation layouts."""
from pathlib import Path

import pytest

from robustness.synthetic import make_bars, bars_to_ts_text, make_trades, trades_to_report_text  # noqa: F401 - re-exported for tests

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mini_report_text() -> str:
    return (FIXTURES / "mini_report.csv").read_bytes().decode("utf-8")


@pytest.fixture
def mini_bars_text() -> str:
    return (FIXTURES / "mini_bars.txt").read_bytes().decode("utf-8")
