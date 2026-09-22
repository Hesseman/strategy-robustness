"""Per-side transaction-cost reference, copied verbatim from the MultiWalk symbol lists
(E:/MultiWalk/Program/SymbolListWithCommissions.txt + SymbolListWithSlippage.txt,
dated 2024-12-02), read as dollars per side per contract. Only reason to change: those
lists change. Do not reason from tick counts - copy the list values. The same values
(minus the micros) live in le-trading-research/signal_lab/robustness/costs.py."""
from __future__ import annotations

import re

# root: (commission $/side/contract, slippage $/side/contract)
PER_SIDE_USD: dict[str, tuple[float, float]] = {
    "AD": (2.5, 12.5), "BO": (2.5, 10.0), "BP": (2.5, 10.0), "BRN": (2.5, 15.0), "BTC": (2.5, 250.0),
    "C": (2.5, 12.5), "CC": (2.5, 15.0), "CD": (2.5, 12.5), "CL": (2.5, 15.0), "CT": (2.5, 20.0),
    "DA": (2.5, 80.0), "DX": (2.5, 10.0), "EC": (2.5, 15.0), "EMD": (2.5, 25.0), "ES": (2.5, 12.5),
    "FC": (2.5, 45.0), "FDAX": (2.5, 25.0), "FDXM": (2.5, 10.0), "FESX": (2.5, 10.0), "FGBL": (2.5, 10.0),
    "FGBM": (2.5, 10.0), "FGBS": (2.5, 5.0), "FGBX": (2.5, 30.0), "FSTB": (2.5, 5.0), "FSTU": (2.5, 15.0),
    "FV": (2.5, 10.0), "GC": (2.5, 30.0), "HG": (2.5, 17.5), "HO": (2.5, 32.5), "JY": (2.5, 15.0),
    "KC": (2.5, 35.0), "KW": (2.5, 17.5), "LB": (2.5, 250.0), "LC": (2.5, 20.0), "LH": (2.5, 30.0),
    "MP1": (2.5, 12.5), "NE1": (2.5, 10.0), "NG": (2.5, 17.5), "NK": (2.5, 30.0), "NQ": (2.5, 15.0),
    "O": (2.5, 50.0), "OJ": (2.5, 75.0), "PA": (2.5, 250.0), "PL": (2.5, 25.0), "RB": (2.5, 37.5),
    "RR": (2.5, 50.0), "RTY": (2.5, 20.0), "S": (2.5, 15.0), "SB": (2.5, 12.5), "SF": (2.5, 17.5),
    "SI": (2.5, 32.5), "SM": (2.5, 15.0), "TF": (2.5, 20.0), "TU": (2.5, 10.0), "TY": (2.5, 17.5),
    "US": (2.5, 32.5), "VX": (2.5, 50.0), "W": (2.5, 15.0), "YM": (2.5, 10.0),
    "MES": (0.62, 1.875), "MNQ": (0.62, 2.25), "M2K": (0.62, 3.0), "MYM": (0.62, 1.5), "MBT": (0.62, 7.5),
    "MET": (0.62, 0.375), "E7": (0.62, 11.25), "M6E": (0.62, 2.25), "J7": (0.62, 11.25), "M6B": (0.62, 1.5),
    "M6A": (0.62, 1.875), "MGC": (0.62, 4.5), "SIL": (0.62, 9.75), "MHG": (0.62, 2.625), "QM": (0.62, 11.25),
    "MCL": (0.62, 2.25), "QN": (0.62, 6.5625), "YW": (0.62, 4.5), "YC": (0.62, 3.75), "YK": (0.62, 4.5),
}

_ROOT = re.compile(r"^@?([A-Z0-9]+?)(?:[FGHJKMNQUVXZ]\d{2})?$")


def normalize_root(symbol: str) -> str:
    """'@MNQ' -> 'MNQ'; 'MNQZ26' -> 'MNQ' (month code + 2-digit year stripped); case-insensitive."""
    s = (symbol or "").strip().upper()
    m = _ROOT.match(s)
    return m.group(1) if m else s.lstrip("@")


def round_trip_usd(symbol: str) -> float | None:
    """Reference round-trip cost per contract = 2 x (commission + slippage), or None when the
    symbol's root is not in the MultiWalk table."""
    cfg = PER_SIDE_USD.get(normalize_root(symbol))
    return None if cfg is None else round(2 * (cfg[0] + cfg[1]), 4)
