"""Card copy - text only. Adapted from the ES RSI(2) deck's per-test slides."""
CARDS = {
    "baseline": {
        "title": "Baseline - edge is measured against the drift, not against zero",
        "tagline": "Every card below scores lift = the strategy's return minus what random timing earns",
        "catches": "A long strategy on a rising market shows positive returns by construction; a win rate proves nothing by itself.",
        "how": "For every trade, the average return a random entry with the same hold length and direction would have earned over the whole bar history. Lift is the strategy's mean minus that. Per-contract % of price, so early and late years weigh the same.",
    },
    "t8a": {
        "title": "T8a - Random entries: is it timing, or just being in the market?",
        "tagline": "Luck - build the distribution of what random timing achieves and see where the strategy lands",
        "catches": "N trades can beat the drift by chance. We need to know how much N random entries vary, and whether the strategy's mean is inside that range.",
        "how": "Draw one random entry bar per trade, hold it for that trade's own number of bars in its own direction, take the mean; repeat 1000 times. p = (random sets at least as good + 1) / (sets + 1) - the strategy's own result counts as one more draw, so p never reads exactly 0: 0 of 1000 shows as p ≤ 0.001. Gate: p < 0.05. It takes the strategy as given - it does not know how many strategies were tried.",
    },
    "t3": {
        "title": "T3 - Does it work in every era, and in a crisis?",
        "tagline": "Instability - an average over ten years can hide an edge that lived in one regime",
        "catches": "An edge concentrated in one bull run, or one that faded after a rule change, still averages positive over the full sample.",
        "how": "Split the bars into four equal windows and recompute lift in each (against that window's own drift); score = windows with positive lift. Crisis split: trades entered on top-decile volatility bars (20-bar rolling) versus the rest. Plus $ per calendar year for one contract.",
    },
    "t7": {
        "title": "T7 - Costs: how much friction would it take to kill it?",
        "tagline": "Friction - an assumption haircut and a stress test, not an execution simulation",
        "catches": "A real but tiny edge is a donation to the broker. One tick of slippage is easy on a quiet day and wrong on a panic day.",
        "how": "Every trade is haircut by the instrument's reference round-trip cost (commission + slippage, both sides, from the MultiWalk symbol lists). Gate: net lift over the drift after 1x cost > 0. Then multiply the cost until the lift disappears - the break-even multiplier is the margin of safety.",
    },
    "drawdown": {
        "title": "Drawdown & capital - what does it take to hold this strategy?",
        "tagline": "Sizing - one contract, dollar P&L, discrete drawdown episodes",
        "catches": "A single worst drawdown is one unstable number; an average drawdown hides the tail. Neither tells you what account size the strategy needs.",
        "how": "Cumulative $ P&L for one contract by trade close -> peak-to-recovery drawdown episodes -> CDaR-80 (mean of the worst 20% of episodes) -> capital = 5 x CDaR-80 -> annual % on that capital. Sharpe, Sortino, Calmar and profit per average drawdown are for ranking strategies, not for sizing. The margin line uses today's margin only and says nothing about the past.",
    },
    "timing_entry": {
        "title": "Entry delay - does the edge live in the first bars after the signal?",
        "tagline": "Execution sensitivity - the same trades, entered 1, 2, ... bars late, exits as reported",
        "catches": "An edge that collapses within 1-2 bars of delay lives in the signal bar itself: it is exposed to latency and slippage on entry and, on slow bar sizes, is a warning sign for look-ahead in the signal. An edge that barely moves means the entry is a coarse regime filter, not a timing call.",
        "how": "Every trade's entry moves k bars later and fills at the open of that bar; the exit keeps its reported bar and price (the exit rule is treated as a time-fixed signal - we cannot re-run the strategy's stops and targets). A trade whose delayed entry reaches its exit bar is skipped at that k and counted. In 'fixed hold' mode the exit moves k bars too, at the open, so the hold length is kept. Gross $, one contract, no costs: costs move the curve's level, not its shape. Trades are independent - no position limit.",
    },
    "timing_exit": {
        "title": "Exit delay - is the exit precisely timed?",
        "tagline": "Exit sensitivity - the same trades, closed 1, 2, ... bars late, entries as reported",
        "catches": "If a later exit improves the return, the exit rule fires early relative to the move. If it destroys the return, the exit is precisely timed (a stop or a target) and slippage on the exit bar matters more than on the entry bar.",
        "how": "Every trade keeps its reported entry; its exit moves k bars later and fills at the open of that bar. A trade whose delayed exit falls past the last bar is skipped at that k and counted. A delayed exit may overlap the next trade's entry - trades are treated as independent. Gross $, one contract, no costs. Identical in both modes.",
    },
}
