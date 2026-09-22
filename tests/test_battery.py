import json

import pandas as pd
import pytest

from robustness.bars_loader import load_bars
from robustness.battery import GATE_ALPHA, ValidationFailed, run_battery, to_json
from robustness.report_parser import parse_report
from conftest import make_bars, make_trades, bars_to_ts_text, trades_to_report_text


def _battery(planted_edge, n=80, **kw):
    bars = make_bars(n=4000, seed=30)
    trades = make_trades(bars, n=n, seed=31, planted_edge=planted_edge)
    rep = parse_report(trades_to_report_text(trades))
    return run_battery(rep, load_bars(bars_to_ts_text(bars)), n_perm=500, seed=0, **kw)


def test_planted_edge_passes_t8a_gate():
    r = _battery(planted_edge=True)
    assert r.verdicts["t8a"] == "pass" and r.baseline.p_value < GATE_ALPHA
    assert r.verdicts["baseline"] == "reference" and r.verdicts["t3"] == "score" and r.verdicts["drawdown"] == "reference"
    assert r.verdicts["t7"] in ("pass", "fail")
    assert r.gates_total == 2 and r.gates_passed == sum(v == "pass" for k, v in r.verdicts.items() if k in ("t8a", "t7"))
    assert r.meta["symbol"] == "@MNQ" and r.meta["root"] == "MNQ" and r.meta["point_value"] == 2.0
    assert r.t7.cost_source == "multiwalk" and r.t7.cost_rt_usd == 5.74
    assert r.meta["n_trades"] == r.baseline.n_trades == r.dd.n_trades
    assert "multiple-testing" in r.caveat


def test_insufficient_trades_disables_gates():
    r = _battery(planted_edge=True, n=20)
    assert r.verdicts["t8a"] == "insufficient" and r.verdicts["t7"] == "insufficient"
    assert r.gates_passed == 0


def test_unknown_symbol_falls_back_to_report_costs():
    bars = make_bars(n=3000, seed=32)
    trades = make_trades(bars, n=40, seed=33)
    rep = parse_report(trades_to_report_text(trades, symbol="@ZZZ"))
    r = run_battery(rep, load_bars(bars_to_ts_text(bars)), n_perm=200)
    assert r.t7.cost_source == "report" and r.t7.cost_rt_usd == pytest.approx(5.40)


def test_margin_line_optional():
    assert _battery(planted_edge=False, n=40).margin is None
    r = _battery(planted_edge=False, n=40, today_margin_usd=2500.0)
    assert r.margin["today_margin_usd"] == 2500.0 and r.margin["capital_usd"] == r.dd.capital


def test_validation_failure_raises_with_checks():
    bars = make_bars(n=3000, seed=34)
    trades = make_trades(bars, n=40, seed=35)
    rep = parse_report(trades_to_report_text(trades))
    short_bars = load_bars(bars_to_ts_text(bars.iloc[: len(bars) // 2]))
    with pytest.raises(ValidationFailed) as ei:
        run_battery(rep, short_bars, n_perm=100)
    assert any(c.name == "timestamps_found" and not c.passed for c in ei.value.checks)


def test_to_json_roundtrips():
    r = _battery(planted_edge=True, n=40)
    d = json.loads(to_json(r))
    assert set(d) >= {"meta", "checks", "baseline", "t3", "t7", "dd", "verdicts", "gates_passed", "gates_total", "caveat"}
    assert d["baseline"]["n_perm"] == 500 and len(d["baseline"]["null"]) == 500
    assert isinstance(d["dd"]["worst"]["peak_time"], str)
    assert d["t3"]["yearly"][0].keys() >= {"year", "usd", "n"}
