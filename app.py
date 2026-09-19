import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Pocket Option Signal Bot V1", page_icon="📊", layout="centered")

st.title("📊 Pocket Option Signal Bot V1")
st.caption("Signal-only educational tool — it does not place trades.")

st.warning("Signals are estimates, not guarantees. Test on demo data before risking money.")

uploaded = st.file_uploader(
    "Upload an OHLC CSV file with columns: open, high, low, close",
    type=["csv"]
)

def add_indicators(df):
    df = df.copy()
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi14"] = 100 - (100 / (1 + rs))
    return df

def make_signal(row):
    bullish = row["close"] > row["open"]
    bearish = row["close"] < row["open"]
    trend_up = row["ema9"] > row["ema21"]
    trend_down = row["ema9"] < row["ema21"]
    rsi = row["rsi14"]

    if pd.isna(rsi):
        return "NO TRADE", 0, "Not enough candles to calculate RSI."

    if bullish and trend_up and 50 <= rsi <= 70:
        return "CALL", 65, "Bullish candle, upward EMA trend, and RSI supports momentum."
    if bearish and trend_down and 30 <= rsi <= 50:
        return "PUT", 65, "Bearish candle, downward EMA trend, and RSI supports momentum."

    return "NO TRADE", 40, "Conditions are mixed or outside the basic filter."

if uploaded:
    try:
        df = pd.read_csv(uploaded)
        df.columns = [c.strip().lower() for c in df.columns]
        required = {"open", "high", "low", "close"}

        if not required.issubset(df.columns):
            st.error("Your CSV must contain open, high, low, and close columns.")
        elif len(df) < 25:
            st.error("Please upload at least 25 candles.")
        else:
            for col in required:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=list(required))
            df = add_indicators(df)
            latest = df.iloc[-1]
            signal, confidence, reason = make_signal(latest)

            st.subheader("Latest Signal")
            st.metric("Action", signal)
            st.metric("Confidence estimate", f"{confidence}%")
            st.write("**Reason:**", reason)

            st.subheader("Latest Candle Data")
            st.dataframe(df.tail(10), use_container_width=True)
    except Exception as exc:
        st.error(f"Could not read the file: {exc}")
else:
    st.info("Upload a candle CSV to generate a signal.")
