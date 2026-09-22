import numpy as np
from conftest import make_bars, make_trades, bars_to_ts_text, trades_to_report_text


def test_generator_roundtrip_shapes():
    bars = make_bars(n=500, seed=3)
    trades = make_trades(bars, n=20, seed=4)
    assert (trades.exit_idx > trades.entry_idx).all()
    assert (trades.entry_idx.to_numpy()[1:] > trades.exit_idx.to_numpy()[:-1]).all()  # non-overlapping
    text = trades_to_report_text(trades)
    assert "#,Type,Date/Time" in text and text.count("\r\n") > 40
    assert bars_to_ts_text(bars).splitlines()[0].startswith('"Date","Time"')
    gross = trades.direction * (trades.exit_price - trades.entry_price) * 2.0 * trades.contracts
    assert np.allclose(gross.round(2), trades.gross_pnl)
