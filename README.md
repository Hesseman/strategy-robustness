# Strategy Robustness App

Upload a TradeStation **Strategy Performance Report** (saved as CSV) and the **bar data** the
strategy ran on (Data Window export, same symbol and interval). The app joins the trade list
to the bars and runs the trade-list subset of our robustness battery:

| Card | Question | Verdict type |
|---|---|---|
| Baseline | edge vs the drift, not vs zero | reference |
| T8a random entries | better than random timing with the same holds? | gate: p < 0.05 |
| T3 eras + crisis | every era? high-volatility bars? | score: k of 4 windows |
| T7 cost stress | how much friction kills it? | gate: net lift after 1× cost > 0 |
| Drawdown & capital | CDaR-80, capital = 5 × CDaR-80, annual % | reference |

The tests take the strategy as given. They do not know how many strategies or parameter sets
were tried, so there is no multiple-testing correction — a pass means "we could not break it
with these tests", not "it works".

## Run (Docker)

    docker build -t strategy-robustness .
    docker run --rm -p 8501:8501 strategy-robustness

Open http://localhost:8501. Nothing is stored; uploads live in memory for the session.

## Develop

    py -3.13 -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.txt
    .venv/Scripts/python -m pytest -q
    .venv/Scripts/python -m streamlit run app/streamlit_app.py

Dev-only: set `SR_SAMPLE_REPORT` and `SR_SAMPLE_BARS` to local file paths and a
"Load sample files" button appears. Real report/bar files are never committed.

Design: `C:/Projects/docs/superpowers/specs/2026-09-21-strategy-robustness-app-design.md`.
