import os
import json
import pandas as pd
import streamlit as st


# ---------------------------------------------------------
# TriadFlux R9 Dashboard
# ---------------------------------------------------------

st.set_page_config(
    page_title="TriadFlux R9",
    page_icon="📈",
    layout="wide",
)

st.title("TriadFlux R9")
st.caption(
    "Regime-adaptive trading engine • 3 parallel strategies • "
    "regime attribution • paper trading"
)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

LOG_FILE = "logs/paper_decisions.jsonl"


# ---------------------------------------------------------
# Load paper decisions
# ---------------------------------------------------------

def load_decisions():
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame()

    rows = []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    except Exception as exc:
        st.error(f"Could not read decision log: {exc}")
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

df = load_decisions()


# ---------------------------------------------------------
# Empty state
# ---------------------------------------------------------

if df.empty:
    st.info(
        "No paper decisions yet. Start bitget_live_runner.py "
        "to generate decisions."
    )
    st.stop()


# ---------------------------------------------------------
# Latest decision
# ---------------------------------------------------------

latest = df.iloc[-1]


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def get_signal(side):
    try:
        side_value = int(side)

        if side_value == 1:
            return "BUY"
        elif side_value == -1:
            return "SELL"
        else:
            return "NO TRADE"

    except Exception:
        return "NO TRADE"


def safe_float(value, digits=4):
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


# ---------------------------------------------------------
# Header metrics
# ---------------------------------------------------------

regime = latest["regime"] if "regime" in latest else "UNKNOWN"

confidence = (
    latest["regime_confidence"]
    if "regime_confidence" in latest
    else 0
)

best_strategy = (
    latest["best_strategy"]
    if "best_strategy" in latest
    else "none"
)

side = latest["side"] if "side" in latest else 0

signal = get_signal(side)


c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Regime",
        str(regime),
    )

with c2:
    st.metric(
        "Confidence",
        safe_float(confidence, 2),
    )

with c3:
    st.metric(
        "Best strategy",
        str(best_strategy),
    )

with c4:
    st.metric(
        "Signal",
        signal,
    )


# ---------------------------------------------------------
# Decision details
# ---------------------------------------------------------

st.subheader("Decision details")

d1, d2, d3, d4 = st.columns(4)

with d1:
    st.write("**Symbol**")
    st.write(
        str(latest["symbol"])
        if "symbol" in latest
        else "—"
    )

with d2:
    st.write("**Interval**")
    st.write(
        str(latest["interval"])
        if "interval" in latest
        else "—"
    )

with d3:
    st.write("**Execution mode**")
    st.write(
        str(latest["mode"])
        if "mode" in latest
        else "PAPER"
    )

with d4:
    st.write("**Aggregate score**")
    st.write(
        safe_float(
            latest["aggregate_score"],
            4,
        )
        if "aggregate_score" in latest
        else "—"
    )


# ---------------------------------------------------------
# Price / risk information
# ---------------------------------------------------------

st.subheader("Trade levels")

p1, p2, p3, p4 = st.columns(4)

with p1:
    st.write("**Entry**")
    st.write(
        safe_float(latest["entry"], 4)
        if "entry" in latest
        else "—"
    )

with p2:
    st.write("**Stop**")
    st.write(
        safe_float(latest["stop"], 4)
        if "stop" in latest and pd.notna(latest["stop"])
        else "—"
    )

with p3:
    st.write("**Target**")
    st.write(
        safe_float(latest["target"], 4)
        if "target" in latest and pd.notna(latest["target"])
        else "—"
    )

with p4:
    st.write("**Position size**")
    st.write(
        safe_float(latest["size"], 4)
        if "size" in latest
        else "—"
    )


# ---------------------------------------------------------
# Timing information
# ---------------------------------------------------------

st.subheader("Timing")

t1, t2 = st.columns(2)

with t1:
    st.write("**Market candle**")
    st.write(
        str(latest["timestamp"])
        if "timestamp" in latest
        else "—"
    )

with t2:
    st.write("**Observed at**")
    st.write(
        str(latest["observed_at"])
        if "observed_at" in latest
        else "—"
    )


# ---------------------------------------------------------
# Strategy signals
# ---------------------------------------------------------

st.subheader("Parallel strategy signals")

strategy_signals = latest.get("strategy_signals", [])

if isinstance(strategy_signals, str):
    try:
        strategy_signals = json.loads(strategy_signals)
    except Exception:
        strategy_signals = []

if strategy_signals:

    strategy_rows = []

    for item in strategy_signals:

        if not isinstance(item, dict):
            continue

        item_side = item.get("side", 0)

        strategy_rows.append(
            {
                "Strategy": item.get(
                    "strategy",
                    "unknown",
                ),
                "Side": get_signal(item_side),
                "Score": item.get(
                    "score",
                    0,
                ),
                "Reason": item.get(
                    "reason",
                    "",
                ),
            }
        )

    if strategy_rows:
        strategy_df = pd.DataFrame(strategy_rows)

        st.dataframe(
            strategy_df,
            use_container_width=True,
            hide_index=True,
        )

else:
    st.info(
        "No strategy signal details were recorded "
        "for the latest decision."
    )


# ---------------------------------------------------------
# Decision reasoning
# ---------------------------------------------------------

st.subheader("Decision reasoning")

reasons = latest.get("reasons", [])

if isinstance(reasons, str):
    try:
        reasons = json.loads(reasons)
    except Exception:
        reasons = [reasons]

if isinstance(reasons, list) and reasons:

    for reason in reasons:
        st.write(f"• {reason}")

else:
    st.write("No additional reasoning recorded.")


# ---------------------------------------------------------
# Regime scorecard
# ---------------------------------------------------------

st.subheader("Regime strategy scorecard")

scorecard = latest.get("scorecard", [])

if isinstance(scorecard, str):

    try:
        scorecard = json.loads(scorecard)
    except Exception:
        scorecard = []

if isinstance(scorecard, list) and scorecard:

    scorecard_df = pd.DataFrame(scorecard)

    st.dataframe(
        scorecard_df,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "Scorecard is currently empty. "
        "TriadFlux needs completed paper-trade outcomes "
        "before regime-specific performance statistics "
        "can accumulate."
    )


# ---------------------------------------------------------
# Recent decision history
# ---------------------------------------------------------

st.subheader("Recent decision history")

history = df.tail(200).copy()

# Convert complex JSON columns into readable text
for column in [
    "reasons",
    "strategy_signals",
    "scorecard",
]:

    if column in history.columns:

        history[column] = history[column].apply(
            lambda value: json.dumps(value, default=str)
            if isinstance(value, (list, dict))
            else str(value)
        )


# Add human-readable signal column
if "side" in history.columns:

    history["signal"] = history["side"].apply(
        get_signal
    )


# Select useful columns first
preferred_columns = [
    "timestamp",
    "symbol",
    "interval",
    "mode",
    "regime",
    "regime_confidence",
    "best_strategy",
    "aggregate_score",
    "signal",
    "entry",
    "stop",
    "target",
    "size",
    "close",
    "observed_at",
]

available_columns = [
    column
    for column in preferred_columns
    if column in history.columns
]

if available_columns:

    st.dataframe(
        history[available_columns],
        use_container_width=True,
        hide_index=True,
    )

else:

    st.dataframe(
        history,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------

st.divider()

st.caption(
    "TriadFlux R9 is currently operating in PAPER mode. "
    "No live orders are submitted by this dashboard."
)

st.caption(
    f"Decision records loaded: {len(df)}"
)