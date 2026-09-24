import streamlit as st
import pandas as pd
import numpy as np
from urllib.parse import urlencode
from urllib.request import urlopen
import json

# -----------------------------
# PAGE SETUP
# -----------------------------
st.set_page_config(
    page_title="Pocket Option Signal Bot V1 LIVE",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Pocket Option Signal Bot V1 — LIVE")
st.caption(
    "Live open-market forex signal dashboard. "
    "It does not place trades or access your Pocket Option account."
)

st.warning(
    "Signals are estimates, not guarantees. "
    "Always verify the current price and candle before entering a trade."
)

# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.header("⚙️ Live Market Setup")

api_key = st.sidebar.text_input(
    "Twelve Data API Key",
    type="password"
)

symbol = st.sidebar.selectbox(
    "Forex Pair",
    [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "USD/CAD",
        "USD/CHF",
        "NZD/USD"
    ]
)

timeframe = st.sidebar.selectbox(
    "Candle Timeframe",
    [
        "1min",
        "5min",
        "15min"
    ],
    index=0
)

st.sidebar.info(
    "Your API key is entered here and is not written into this GitHub file."
)

# -----------------------------
# GET LIVE MARKET DATA
# -----------------------------
def get_market_data(api_key, symbol, interval):

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 100,
        "timezone": "America/Port_of_Spain",
        "apikey": api_key
    }

    url = (
        "https://api.twelvedata.com/time_series?"
        + urlencode(params)
    )

    with urlopen(url, timeout=15) as response:
        data = json.loads(
            response.read().decode("utf-8")
        )

    if data.get("status") == "error":
        raise Exception(
            data.get(
                "message",
                "Market-data API returned an error."
            )
        )

    values = data.get("values")

    if not values:
        raise Exception(
            "No market candles were returned."
        )

    df = pd.DataFrame(values)

    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    for column in [
        "open",
        "high",
        "low",
        "close"
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "datetime",
            "open",
            "high",
            "low",
            "close"
        ]
    )

    df = df.sort_values(
        "datetime"
    ).reset_index(drop=True)

    return df


# -----------------------------
# TECHNICAL INDICATORS
# -----------------------------
def add_indicators(df):

    df = df.copy()

    # EMA
    df["ema9"] = (
        df["close"]
        .ewm(span=9, adjust=False)
        .mean()
    )

    df["ema21"] = (
        df["close"]
        .ewm(span=21, adjust=False)
        .mean()
    )

    df["ema50"] = (
        df["close"]
        .ewm(span=50, adjust=False)
        .mean()
    )

    # RSI
    delta = df["close"].diff()

    gain = (
        delta.clip(lower=0)
        .rolling(14)
        .mean()
    )

    loss = (
        -delta.clip(upper=0)
    ).rolling(14).mean()

    rs = gain / loss.replace(
        0,
        np.nan
    )

    df["rsi14"] = (
        100 -
        (100 / (1 + rs))
    )

    # MACD
    ema12 = (
        df["close"]
        .ewm(span=12, adjust=False)
        .mean()
    )

    ema26 = (
        df["close"]
        .ewm(span=26, adjust=False)
        .mean()
    )

    df["macd"] = ema12 - ema26

    df["macd_signal"] = (
        df["macd"]
        .ewm(span=9, adjust=False)
        .mean()
    )

    # Candle measurements
    df["body"] = (
        df["close"] -
        df["open"]
    ).abs()

    df["range"] = (
        df["high"] -
        df["low"]
    ).replace(0, np.nan)

    df["upper_wick"] = (
        df["high"] -
        df[["open", "close"]].max(axis=1)
    )

    df["lower_wick"] = (
        df[["open", "close"]].min(axis=1) -
        df["low"]
    )

    return df


# -----------------------------
# CANDLE PATTERN
# -----------------------------
def candle_pattern(row):

    if pd.isna(row["range"]):
        return "Unknown"

    if row["body"] <= row["range"] * 0.15:
        return "Doji / Indecision"

    if (
        row["lower_wick"] >= row["body"] * 2
        and
        row["upper_wick"] <= row["body"]
    ):
        return "Possible Hammer"

    if (
        row["upper_wick"] >= row["body"] * 2
        and
        row["lower_wick"] <= row["body"]
    ):
        return "Possible Shooting Star"

    if row["close"] > row["open"]:
        return "Bullish Candle"

    return "Bearish Candle"


# -----------------------------
# SIGNAL ENGINE
# -----------------------------
def generate_signal(df):

    if len(df) < 60:

        return (
            "NO TRADE",
            0,
            "Not enough candles.",
            "UNKNOWN",
            "Unknown"
        )

    current = df.iloc[-1]
    previous = df.iloc[-2]

    required = [
        "ema9",
        "ema21",
        "ema50",
        "rsi14",
        "macd",
        "macd_signal"
    ]

    if current[required].isna().any():

        return (
            "NO TRADE",
            0,
            "Indicator data is incomplete.",
            "UNKNOWN",
            candle_pattern(current)
        )

    call_score = 0
    put_score = 0

    reasons = []

    # EMA TREND
    if (
        current["ema9"] >
        current["ema21"] >
        current["ema50"]
    ):

        call_score += 2
        reasons.append(
            "EMA trend is bullish"
        )

    elif (
        current["ema9"] <
        current["ema21"] <
        current["ema50"]
    ):

        put_score += 2
        reasons.append(
            "EMA trend is bearish"
        )

    # MACD
    if current["macd"] > current["macd_signal"]:

        call_score += 1
        reasons.append(
            "MACD bullish"
        )

    elif current["macd"] < current["macd_signal"]:

        put_score += 1
        reasons.append(
            "MACD bearish"
        )

    # CANDLE
    if current["close"] > current["open"]:

        call_score += 1
        reasons.append(
            "Current candle bullish"
        )

    elif current["close"] < current["open"]:

        put_score += 1
        reasons.append(
            "Current candle bearish"
        )

    # RSI
    if 50 <= current["rsi14"] <= 68:

        call_score += 1
        reasons.append(
            "RSI supports upward momentum"
        )

    elif 32 <= current["rsi14"] < 50:

        put_score += 1
        reasons.append(
            "RSI supports downward momentum"
        )

    # BREAKOUT
    if current["close"] > previous["high"]:

        call_score += 1
        reasons.append(
            "Close above previous high"
        )

    elif current["close"] < previous["low"]:

        put_score += 1
        reasons.append(
            "Close below previous low"
        )

    strongest = max(
        call_score,
        put_score
    )

    difference = abs(
        call_score -
        put_score
    )

    # NO TRADE
    if (
        strongest < 4
        or
        difference < 2
    ):

        return (
            "NO TRADE",
            min(
                59,
                40 + strongest * 4
            ),
            "Mixed confirmation: "
            + "; ".join(reasons[:5]),
            "MIXED",
            candle_pattern(current)
        )

    # SIGNAL
    if call_score > put_score:

        action = "CALL"
        trend = "UP"

    else:

        action = "PUT"
        trend = "DOWN"

    confidence = min(
        85,
        55 +
        strongest * 5 +
        difference * 3
    )

    return (
        action,
        confidence,
        "; ".join(reasons[:5]),
        trend,
        candle_pattern(current)
    )


# -----------------------------
# LIVE DASHBOARD
# -----------------------------
if not api_key:

    st.info(
        "👈 Enter your Twelve Data API key "
        "in the sidebar to connect to the live market."
    )

    st.markdown(
        """
        ### What this V1 will do

        **Live EUR/USD → 1-minute candles → technical analysis → signal**

        The signal engine checks:

        - EMA 9 / 21 / 50
        - RSI 14
        - MACD
        - Candle direction
        - Previous-candle breakout
        - Candle pattern

        It can return:

        **CALL**

        **PUT**

        **NO TRADE**
        """
    )

else:

    try:

        df = get_market_data(
            api_key,
            symbol,
            timeframe
        )

        df = add_indicators(df)

        (
            action,
            confidence,
            reason,
            trend,
            pattern
        ) = generate_signal(df)

        latest = df.iloc[-1]

        st.success(
            f"🟢 LIVE MARKET CONNECTED — "
            f"{symbol} — {timeframe}"
        )

        # -------------------------
        # MAIN METRICS
        # -------------------------

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "SIGNAL",
            action
        )

        col2.metric(
            "Confidence",
            f"{confidence}%"
        )

        col3.metric(
            "Current Price",
            f"{latest['close']:.5f}"
        )

        col4.metric(
            "Trend",
            trend
        )

        # -------------------------
        # SIGNAL DETAILS
        # -------------------------

        st.subheader(
            "📌 Signal Details"
        )

        st.write(
            "**Candle Pattern:**",
            pattern
        )

        st.write(
            "**Reason:**",
            reason
        )

        if action == "CALL":

            st.success(
                "📈 CALL — The current rule set "
                "detects upward conditions."
            )

        elif action == "PUT":

            st.error(
                "📉 PUT — The current rule set "
                "detects downward conditions."
            )

        else:

            st.warning(
                "⏸️ NO TRADE — Confirmation is "
                "not strong enough."
            )

        # -------------------------
        # INDICATORS
        # -------------------------

        st.subheader(
            "📊 Indicator Snapshot"
        )

        indicators = pd.DataFrame({

            "Indicator": [
                "EMA 9",
                "EMA 21",
                "EMA 50",
                "RSI 14",
                "MACD",
                "MACD Signal"
            ],

            "Value": [

                latest["ema9"],
                latest["ema21"],
                latest["ema50"],
                latest["rsi14"],
                latest["macd"],
                latest["macd_signal"]

            ]

        })

        st.dataframe(
            indicators.round(5),
            use_container_width=True,
            hide_index=True
        )

        # -------------------------
        # RECENT CANDLES
        # -------------------------

        st.subheader(
            "🕯️ Recent Market Candles"
        )

        candle_columns = [
            "datetime",
            "open",
            "high",
            "low",
            "close"
        ]

        st.dataframe(
            df[candle_columns].tail(10),
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            f"Last candle received: "
            f"{latest['datetime']}"
        )

        # -------------------------
        # REFRESH
        # -------------------------

        if st.button(
            "🔄 Refresh Market"
        ):

            st.rerun()

        st.caption(
            "Market data is supplied by Twelve Data. "
            "The signal is rule-based and is not a guaranteed "
            "prediction of the next candle."
        )

    except Exception as error:

        st.error(
            f"❌ Live market connection failed: {error}"
        )

        st.info(
            "Check that your Twelve Data API key is correct "
            "and that the selected forex pair is available."
        )
