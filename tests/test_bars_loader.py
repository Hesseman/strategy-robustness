import pandas as pd
import pytest

from robustness.bars_loader import BarsFormatError, infer_interval, load_bars
from conftest import make_bars, bars_to_ts_text


def test_mini_bars(mini_bars_text):
    b = load_bars(mini_bars_text)
    assert list(b.columns) == ["open", "high", "low", "close", "volume"]
    assert b.index.name == "ts" and b.index.is_monotonic_increasing and b.index.is_unique
    assert len(b) == 17
    assert b.loc[pd.Timestamp("2025-01-06 09:00"), "open"] == 20000.00
    assert b.loc[pd.Timestamp("2025-01-07 13:00"), "low"] == 19996.00
    assert b.loc[pd.Timestamp("2025-01-06 08:30"), "volume"] == 220.0       # Up + Down
    assert "PLOT1" not in b.columns
    assert infer_interval(b) == pd.Timedelta(minutes=30)


def test_daily_layout_with_vol_oi():
    text = ("Date,Time,Open,High,Low,Close,Vol,OI\n"
            "01/02/2025,16:00,100.0,101.0,99.0,100.5,1000,5000\n"
            "01/03/2025,16:00,100.5,102.0,100.0,101.5,1200,5100\n")
    b = load_bars(text)
    assert b.volume.tolist() == [1000.0, 1200.0]
    assert infer_interval(b) == pd.Timedelta(days=1)


def test_synthetic_roundtrip():
    bars = make_bars(n=200, seed=7)
    b = load_bars(bars_to_ts_text(bars))
    assert (b.index == bars.index).all()
    assert b.open.tolist() == bars.open.tolist()


def test_missing_columns_raises():
    with pytest.raises(BarsFormatError, match="missing columns"):
        load_bars("Date,Open,Close\n01/02/2025,1,2\n")


def test_duplicate_timestamp_raises():
    text = ('"Date","Time","Open","High","Low","Close","Up","Down"\n'
            "01/02/2025,09:00,1,2,0.5,1.5,1,1\n01/02/2025,09:00,1,2,0.5,1.5,1,1\n")
    with pytest.raises(BarsFormatError, match="duplicate"):
        load_bars(text)


def test_iso_date_raises_readable_error():
    text = ("Date,Time,Open,High,Low,Close\n"
            "2025-01-06,09:00,1,2,0.5,1.5\n2025-01-06,09:30,1,2,0.5,1.5\n")
    with pytest.raises(BarsFormatError, match="MM/DD/YYYY"):
        load_bars(text)


def test_non_numeric_open_raises_readable_error():
    text = ("Date,Time,Open,High,Low,Close\n"
            "01/06/2025,09:00,bad,2,0.5,1.5\n01/06/2025,09:30,1,2,0.5,1.5\n")
    with pytest.raises(BarsFormatError, match="must be numbers"):
        load_bars(text)
