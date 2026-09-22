# Strategy Robustness App

Upload a TradeStation **Strategy Performance Report** (saved as CSV) and the **bar data** the
strategy ran on (Data Window export, same symbol and interval). The app joins the trade list
to the bars and runs the trade-list subset of our robustness battery. No files? Click **Try
the demo** in the sidebar to run the same battery against a synthetic strategy instead.

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

## Exporting the two files from TradeStation

1. **Strategy Performance Report** — open it for the strategy, then save it as **CSV** (not
   Excel). The app reads its Trades List and Settings.
2. **Bars** — export the chart's Data Window for the **same symbol, same interval, covering
   the whole traded range**. Extra indicator (PLOT) columns are ignored.

Both exports must come from the same workspace so their timestamps agree.

## Run (Docker)

Prerequisite: Docker Desktop.

    docker compose up --build

Open http://localhost:8501. Nothing is stored; uploads live in memory for the session.

Or without compose:

    docker build -t strategy-robustness .
    docker run --rm -p 127.0.0.1:8501:8501 strategy-robustness

Run the test suite inside the built image (no browser needed):

    docker run --rm strategy-robustness python -m pytest -q

## Develop

    py -3.13 -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.txt
    .venv/Scripts/python -m pytest -q
    .venv/Scripts/python -m streamlit run app/streamlit_app.py

Dev-only: set `SR_SAMPLE_REPORT` and `SR_SAMPLE_BARS` to local file paths and a
"Load sample files" button appears. Real report/bar files are never committed.

On Git Bash, prefix the sample `docker run` with `MSYS_NO_PATHCONV=1` so `/samples/...` is
not rewritten.

Design notes: docs/superpowers/specs/2026-09-21-strategy-robustness-app-design.md (in the
C:/Projects estate).
