# Pocket Option Signal Bot V1

A Streamlit educational signal dashboard for analyzing uploaded OHLC candle data.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## CSV format

Your CSV should include:

- open
- high
- low
- close

Optional columns such as time, volume, or timestamp are allowed.

This version is signal-only. It does not connect to Pocket Option, access an account, or place trades.
