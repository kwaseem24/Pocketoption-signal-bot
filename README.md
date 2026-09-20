import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Pocket Option OTC Signal Bot V2", page_icon="📊")
st.title("📊 Pocket Option OTC Signal Bot V2")
st.caption("Signal-only educational tool. It does not place trades or access your account.")
st.warning("Signals are estimates, not guarantees. Test on demo data before risking money.")

st.subheader("Market setup")
st.selectbox("Market", ["OTC"])
timeframe = st.selectbox("Candle timeframe", ["1 minute", "5 minutes", "15 minutes"])
st.info("CSV analysis is available. No verified official live Pocket Option feed is connected yet.")

uploaded = st.file_uploader(
    "Upload an OHLC CSV with open, high, low, close",
    type=["csv"]
)

def add_indicators(df):
    df = df.copy()
    for n in (9, 21, 50):
        df[f"ema{n}"] = df["close"].ewm(span=n, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi14"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    df["body"] = (df["close"] - df["open"]).abs()
    df["range"] = (df["high"] - df["low"]).replace(0, np.nan)
    df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    return df

def candle_pattern(row):
    if pd.isna(row["range"]):
        return "Unknown"
    if row["body"] <= row["range"] * 0.15:
        return "Doji / indecision"
    if row["lower_wick"] >= row["body"] * 2 and row["upper_wick"] <= row["body"]:
        return "Possible hammer"
    if row["upper_wick"] >= row["body"] * 2 and row["lower_wick"] <= row["body"]:
        return "Possible shooting star"
    return "Bullish candle" if row["close"] > row["open"] else "Bearish candle"

def make_signal(df):
    row, previous = df.iloc[-1], df.iloc[-2]
    fields = ["ema9", "ema21", "ema50", "rsi14", "macd", "macd_signal"]
    if row[fields].isna().any():
        return "NO TRADE", 0, "Not enough valid candles.", "UNKNOWN", candle_pattern(row)

    call_score = put_score = 0
    reasons = []

    if row["ema9"] > row["ema21"] > row["ema50"]:
        call_score += 2
        reasons.append("EMA trend up")
    elif row["ema9"] < row["ema21"] < row["ema50"]:
        put_score += 2
        reasons.append("EMA trend down")

    if row["macd"] > row["macd_signal"]:
        call_score += 1
        reasons.append("MACD bullish")
    elif row["macd"] < row["macd_signal"]:
        put_score += 1
        reasons.append("MACD bearish")

    if row["close"] > row["open"]:
        call_score += 1
        reasons.append("bullish candle")
    elif row["close"] < row["open"]:
        put_score += 1
        reasons.append("bearish candle")

    if 50 <= row["rsi14"] <= 68:
        call_score += 1
        reasons.append("RSI supports momentum")
    elif 32 <= row["rsi14"] <= 50:
        put_score += 1
        reasons.append("RSI supports downside")

    if row["close"] > previous["high"]:
        call_score += 1
        reasons.append("close above previous high")
    elif row["close"] < previous["low"]:
        put_score += 1
        reasons.append("close below previous low")

    strongest = max(call_score, put_score)
    difference = abs(call_score - put_score)

    if strongest < 4 or difference < 2:
        return (
            "NO TRADE",
            min(59, 40 + strongest * 4),
            "Insufficient or mixed confirmation: " + "; ".join(reasons[:5]),
            "MIXED",
            candle_pattern(row),
        )

    action = "CALL" if call_score > put_score else "PUT"
    confidence = min(85, 55 + strongest * 5 + difference * 3)
    trend = "UP" if action == "CALL" else "DOWN"
    return action, confidence, "; ".join(reasons[:5]), trend, candle_pattern(row)

if uploaded:
    try:
        df = pd.read_csv(uploaded)
        df.columns = [str(c).strip().lower() for c in df.columns]
        required = {"open", "high", "low", "close"}

        if not required.issubset(df.columns):
            st.error("CSV must contain open, high, low, and close columns.")
        else:
            for column in required:
                df[column] = pd.to_numeric(df[column], errors="coerce")

            df = df.dropna(subset=list(required)).reset_index(drop=True)

            if len(df) < 60:
                st.error("Please upload at least 60 valid candles for V2.")
            else:
                df = add_indicators(df)
                action, confidence, reason, trend, pattern = make_signal(df)

                st.subheader("Latest Signal")
                st.metric("Action", action)
                st.metric("Confidence estimate", f"{confidence}%")

                left, right = st.columns(2)
                left.metric("Trend", trend)
                expiry = {
                    "1 minute": "1–2 minutes",
                    "5 minutes": "5–10 minutes",
                    "15 minutes": "15–30 minutes",
                }[timeframe]
                right.metric("Suggested expiry", "No expiry — wait" if action == "NO TRADE" else expiry)

                st.write("**Candle pattern:**", pattern)
                st.write("**Reason:**", reason)

                latest = df.iloc[-1]
                snapshot = pd.DataFrame({
                    "Indicator": ["EMA 9", "EMA 21", "EMA 50", "RSI 14", "MACD", "MACD signal"],
                    "Value": [
                        latest["ema9"], latest["ema21"], latest["ema50"],
                        latest["rsi14"], latest["macd"], latest["macd_signal"]
                    ],
                })
                st.subheader("Indicator snapshot")
                st.dataframe(snapshot.round(5), use_container_width=True, hide_index=True)

                st.subheader("Recent candle data")
                st.dataframe(df.tail(10), use_container_width=True)

                st.caption(
                    "Confidence is a rule-based score, not a validated win probability. "
                    "Validate the strategy with historical and out-of-sample testing."
                )
    except Exception as exc:
        st.error(f"Could not read the file: {exc}")
else:
    st.info("Upload a candle CSV to generate a V2 analysis.")
