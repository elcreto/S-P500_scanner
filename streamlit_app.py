
import time
import math
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

APP_NAME = "📈 S&P 500 Next‑Day Rise Scanner (Hardcoded)"
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("Now using a hardcoded S&P 500 ticker list. No Wikipedia/CSV dependency.")

# -----------------------------
# Settings
# -----------------------------
with st.sidebar:
    st.subheader("Settings")
    vol_mult = st.number_input("Volume multiple (vs 20‑day avg) ≥", min_value=1.0, value=1.3, step=0.1)
    rr_min = st.number_input("Min Risk/Reward", min_value=1.0, value=2.0, step=0.5)
    max_universe = st.number_input("Max tickers to scan", min_value=50, value=250, step=25)
    sleep_s = st.number_input("Sleep between downloads (sec)", min_value=0.0, value=0.4, step=0.1)
    retries = st.slider("Max retries per ticker", 0, 5, 2)
    days = st.slider("Lookback period (days)", 90, 365, 180)
    show_only_primes = st.checkbox("Show only PRIME (score = 4)", value=False)
    export_filename = st.text_input("Export base filename", "sp500_nextday_scan")

# -----------------------------
# Hardcoded universe
# -----------------------------
UNIVERSE = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'BRK-B', 'UNH', 'XOM', 'LLY', 'JPM', 'V', 'MA', 'HD', 'PG', 'CVX', 'AVGO', 'COST', 'JNJ', 'MRK', 'PEP', 'ABBV', 'KO', 'BAC', 'ADBE', 'WMT', 'NFLX', 'CRM', 'TMO', 'LIN', 'TXN', 'PFE', 'ABT', 'CSCO', 'ACN', 'AMD', 'MCD', 'DHR', 'INTC', 'INTU', 'QCOM', 'LOW', 'AMGN', 'PM', 'HON', 'AMAT', 'BMY', 'IBM', 'GE', 'GS', 'CAT', 'NOW', 'BA', 'ISRG', 'BKNG', 'MDT', 'RTX', 'BLK', 'SPGI', 'PLD', 'DE', 'AMT', 'SYK', 'LMT', 'SCHW', 'MS', 'ADI', 'GILD', 'MU', 'ETN', 'ONTO', 'IONQ']

if len(UNIVERSE) > max_universe:
    universe = UNIVERSE[: int(max_universe)]
else:
    universe = UNIVERSE

st.info(f"Scanning {len(universe)} tickers... (adjust in the sidebar)")

# -----------------------------
# Utils
# -----------------------------
def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def fetch_one(ticker: str, period_days: int, retries: int, sleep: float):
    last_err = None
    for i in range(retries + 1):
        try:
            df = yf.download(
                ticker,
                period=f"{period_days}d",
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = e
        time.sleep(sleep * (i + 1))
    raise RuntimeError(f"{ticker}: {last_err}")

# -----------------------------
# Main loop
# -----------------------------
rows = []
failures = []
progress = st.progress(0)
for idx, t in enumerate(universe, start=1):
    try:
        data = fetch_one(t, days, retries, sleep_s)
        if data.empty or len(data) < 60:
            failures.append((t, "insufficient data"))
            continue

        close = data["Close"]
        vol = data["Volume"]

        # Trend filters
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        c_last = float(close.iloc[-1])
        e20 = float(ema20.iloc[-1])
        e50 = float(ema50.iloc[-1])
        trend_ok = (e20 > e50) and (c_last > e20)

        # MACD
        macd_line, sig_line, hist = macd(close)
        m_last = float(macd_line.iloc[-1])
        s_last = float(sig_line.iloc[-1])
        h_last = float(hist.iloc[-1])
        h_prev = float(hist.iloc[-2])
        macd_ok = (m_last > s_last) and (h_last > 0) and (h_last > h_prev)

        # Volume
        vol_avg20 = vol.rolling(20).mean()
        v_last = float(vol.iloc[-1])
        v_avg = float(vol_avg20.iloc[-1])
        vol_ok = (v_last >= vol_mult * v_avg)

        # R/R
        entry = c_last
        stop = e50
        if stop <= 0 or entry <= stop:
            rr_ok = False
            target = None
            rr = None
        else:
            risk = entry - stop
            target = entry + rr_min * risk
            rr = (target - entry) / risk
            rr_ok = rr >= rr_min

        # Score
        score = int(trend_ok) + int(macd_ok) + int(vol_ok) + int(rr_ok)
        status = "PRIME" if score == 4 else ("Candidate" if score >= 3 else "Pass")

        if (show_only_primes and status == "PRIME") or (not show_only_primes and score >= 3):
            rows.append({
                "Ticker": t,
                "Entry": round(entry, 2),
                "Stop(EMA50)": round(stop, 2) if stop else None,
                "Target": round(target, 2) if target else None,
                "R/R": round(rr, 2) if rr else None,
                "Score": score,
                "Status": status,
            })
    except Exception as e:
        failures.append((t, str(e)))
    if idx % 5 == 0 or idx == len(universe):
        progress.progress(idx / len(universe))

# -----------------------------
# Output
# -----------------------------
if rows:
    df = pd.DataFrame(rows).sort_values(["Status","Score","R/R"], ascending=[True, False, False])
    st.subheader("Results")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name=f"{export_filename}.csv", mime="text/csv")
else:
    st.warning("No PRIME/Candidate tickers found with current thresholds.")
