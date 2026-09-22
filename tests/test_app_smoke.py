"""Headless render of the Streamlit app through streamlit.testing.v1.AppTest, on
synthetic files. Proves the script runs end to end (parse -> battery -> cards)
without a browser; the browser-pane check is the controller's job."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from robustness.synthetic import bars_to_ts_text, make_bars, make_trades, trades_to_report_text

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


def _write_sample(tmp_path):
    bars = make_bars(n=4000, seed=30)
    trades = make_trades(bars, n=80, seed=31, planted_edge=True)
    report, bars_file = tmp_path / "report.csv", tmp_path / "bars.txt"
    report.write_bytes(trades_to_report_text(trades).encode("utf-8"))
    bars_file.write_bytes(bars_to_ts_text(bars).encode("utf-8"))
    return report, bars_file


def test_app_renders_without_files():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, [str(e) for e in at.exception]
    assert any("Upload both files" in el.value for el in at.info)


def test_app_renders_full_battery_on_sample(tmp_path, monkeypatch):
    report, bars_file = _write_sample(tmp_path)
    monkeypatch.setenv("SR_SAMPLE_REPORT", str(report))
    monkeypatch.setenv("SR_SAMPLE_BARS", str(bars_file))
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["sample"] = True
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    text = " ".join(el.value for el in at.markdown)
    assert "Gates passed" in text
    assert "REFERENCE" in text and ("PASS" in text or "FAIL" in text)


def test_app_renders_demo():
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["demo"] = True
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert "Gates passed" in " ".join(el.value for el in at.markdown)
