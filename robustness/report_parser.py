"""Parse a TradeStation Strategy Performance Report saved as CSV.

Only reason to change: TradeStation changes the report layout. Verified layout
(2026-09-21, TradeStation 10, MNQ 30-min sample): sections Performance Summary ·
Trades List · Trade Analysis · periodical returns · Settings; Trades List rows come in
entry/exit pairs (entry row carries the trade number, exit row a blank number);
money as ``$59.10`` / ``($123.40)``; dates ``M/D/YYYY HH:MM`` unpadded.
"""
from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field

import pandas as pd

TRADES_HEADER_PREFIX = "#,Type,Date/Time"
_TRADE_ROW = re.compile(r"^(\d*),(Buy to Cover|Sell Short|Buy|Sell),")
_ENTRY_TYPES = {"Buy": 1, "Sell Short": -1}
_EXIT_FOR = {1: "Sell", -1: "Buy to Cover"}
_DT_FORMATS = ("%m/%d/%Y %H:%M", "%m/%d/%Y")
_N_COLS = 14
_SETTINGS_KEYS = {"Symbol": "symbol", "Interval": "interval", "Start Date/Time": "start",
                  "End Date/Time": "end", "Fixed Shares/Contracts:": "fixed_contracts"}


class ReportFormatError(ValueError):
    """The text is not a TradeStation performance report this app can read."""


@dataclass
class ParsedReport:
    """trades: one row per round-trip trade (see module docstring for columns);
    settings: symbol/interval/dates/strategies/inputs from the Settings block;
    summary: Performance Summary 'All Trades' column, label -> float (money, percent as
    given, counts) or the raw string when not numeric; warnings: non-fatal notes."""
    trades: pd.DataFrame
    settings: dict
    summary: dict
    warnings: list[str] = field(default_factory=list)


def parse_money(s: str) -> float:
    """'$59.10' -> 59.1; '($123.40)' -> -123.4; '-0.34%' -> -0.34; '' / 'n/a' / text -> nan."""
    s = (s or "").strip()
    if s in ("", "n/a"):
        return math.nan
    neg = s.startswith("(") and s.endswith(")")
    body = re.sub(r"[()$,%\s]", "", s)
    try:
        v = float(body)
    except ValueError:
        return math.nan
    return -v if neg else v


def _split(line: str) -> list[str]:
    cells = next(csv.reader([line]))
    return cells + [""] * (_N_COLS - len(cells))


def _parse_dt(s: str, warnings: list[str]) -> pd.Timestamp:
    s = s.strip()
    for fmt in _DT_FORMATS:
        try:
            ts = pd.to_datetime(s, format=fmt)
        except ValueError:
            continue
        if fmt == "%m/%d/%Y":
            note = "Trades List has date-only timestamps (daily strategy?) - joined on date"
            if note not in warnings:
                warnings.append(note)
        return ts
    raise ReportFormatError(f"unrecognised Date/Time {s!r} in Trades List")


def _parse_trades(lines: list[str], header_i: int, warnings: list[str]) -> pd.DataFrame:
    rows: list[list[str]] = []
    for line in lines[header_i + 1:]:
        if not line.strip():
            continue
        if _TRADE_ROW.match(line):
            rows.append(_split(line))
        else:
            break
    if not rows:
        raise ReportFormatError("Trades List header found but no trade rows follow it")
    recs = []
    i = 0
    while i < len(rows):
        e = rows[i]
        if e[0] == "":
            raise ReportFormatError(f"exit row without an entry row at Trades List row {i + 1}")
        j = i + 1
        exits = []
        while j < len(rows) and rows[j][0] == "":
            exits.append(rows[j])
            j += 1
        if len(exits) != 1:
            raise ReportFormatError(f"trade {e[0]} has {len(exits)} exit rows; v1 supports exactly one "
                                    "(scaling out / pyramiding legs are not supported)")
        x = exits[0]
        direction = _ENTRY_TYPES.get(e[1])
        if direction is None:
            raise ReportFormatError(f"trade {e[0]}: entry Type {e[1]!r} is not Buy / Sell Short")
        if x[1] != _EXIT_FOR[direction]:
            raise ReportFormatError(f"trade {e[0]}: exit Type {x[1]!r} does not close a {e[1]}")
        recs.append({
            "trade_id": int(e[0]), "direction": direction,
            "entry_time": _parse_dt(e[2], warnings), "entry_signal": e[3].strip(),
            "entry_price": parse_money(e[4]), "contracts": int(float(e[6])),
            "net_pnl": parse_money(e[7]), "runup_usd": parse_money(e[9]),
            "comm_side": parse_money(e[12]), "slip_side": parse_money(e[13]),
            "exit_time": _parse_dt(x[2], warnings), "exit_signal": x[3].strip(),
            "exit_price": parse_money(x[4]), "gross_pnl": parse_money(x[6]),
            "cum_net_pnl": parse_money(x[7]), "drawdown_usd": parse_money(x[9]),
        })
        i = j
    df = pd.DataFrame(recs)
    if df["entry_price"].isna().any() or df["exit_price"].isna().any():
        raise ReportFormatError("a trade has an unparseable Price")
    return df


def _parse_settings(lines: list[str]) -> dict:
    out: dict = {"symbol": None, "interval": None, "start": None, "end": None,
                 "fixed_contracts": None, "strategies": [], "inputs": {}}
    try:
        s = next(i for i, l in enumerate(lines) if l.strip() == "Settings")
    except StopIteration:
        return out
    mode = None
    for line in lines[s + 1:]:
        if not line.strip():
            continue
        cells = next(csv.reader([line]))
        label = cells[0].strip()
        if label == "TradeStation Strategies Applied":
            mode = "strategies"; continue
        if label == "TradeStation Strategy Settings":
            mode = "inputs"; continue
        if label in ("Trade Size", "TradeStation Report Settings", "TradeStation Chart Settings"):
            mode = None; continue
        if label in _SETTINGS_KEYS and len(cells) > 1:
            out[_SETTINGS_KEYS[label]] = cells[1].strip(); continue
        if not label:
            continue
        if mode == "strategies":
            out["strategies"].append(label)
        elif mode == "inputs" and len(cells) > 1:
            out["inputs"][label] = cells[1].strip()
    return out


def _parse_summary(lines: list[str], end: int) -> dict:
    out: dict = {}
    try:
        s = next(i for i, l in enumerate(lines[:end]) if l.startswith("TradeStation Performance Summary"))
    except StopIteration:
        return out
    for line in lines[s + 1:end]:
        if not line.strip():
            continue
        cells = next(csv.reader([line]))
        label = cells[0].strip()
        if not label or label in out or len(cells) < 2:
            continue
        v = parse_money(cells[1])
        out[label] = cells[1].strip() if math.isnan(v) else v
    return out


def parse_report(text: str) -> ParsedReport:
    """Parse the whole report. Raises ReportFormatError when the Trades List header is
    missing, a trade has != 1 exit row, entry/exit types do not pair, or a price/date does
    not parse. Guarantees: trades sorted as listed, one row per trade, all prices finite."""
    lines = [l.lstrip("\ufeff") for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    try:
        hdr = next(i for i, l in enumerate(lines) if l.startswith(TRADES_HEADER_PREFIX))
    except StopIteration:
        raise ReportFormatError("no TradeStation Trades List header (#,Type,Date/Time,...) found - "
                                "save the performance report as CSV, not Excel") from None
    warnings: list[str] = []
    trades = _parse_trades(lines, hdr, warnings)
    return ParsedReport(trades=trades, settings=_parse_settings(lines),
                        summary=_parse_summary(lines, hdr), warnings=warnings)
