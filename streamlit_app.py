
import time
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

# Embedded ticker universe
EMBEDDED_SP500 = ["AAPL", "ABT", "ACN", "ADBE", "ADI", "AMAT", "AMD", "AMGN", "AMT", "AMZN", "AVGO", "BA", "BAC", "BKNG", "BLK", "BMY", "BRK-B", "CAT", "COST", "CRM", "CSCO", "CVX", "DE", "DHR", "ETN", "GE", "GILD", "GOOGL", "GS", "HD", "HON", "IBM", "INTC", "INTU", "IONQ", "ISRG", "JNJ", "JPM", "KO", "LIN", "LLY", "LMT", "LOW", "MA", "MCD", "MDT", "META", "MRK", "MS", "MSFT", "MU", "NFLX", "NOW", "NVDA", "ONTO", "PEP", "PFE", "PG", "PLD", "PM", "QCOM", "RTX", "SCHW", "SPGI", "SYK", "TMO", "TXN", "UNH", "V", "WMT", "XOM"]

APP_NAME = "📈 S&P 500 Next‑Day Rise Scanner v3.5 (Catalyst Aware)"
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("Scoring 0–5 with Catalyst Override. PRIME, Strong TA, Catalyst PRIME, Candidate.")

# -----------------------------
# Settings
# -----------------------------
with st.sidebar:
    st.subheader("Settings")
    vol_mult = st.number_input("Volume multiple (vs 20‑day avg) ≥", min_value=1.0, value=1.3, step=0.1)
    rr_min = st.number_input("Min Risk/Reward", min_value=1.0, value=2.0, step=0.5)
    max_universe = st.number_input("Max tickers to scan", min_value=20, value=60, step=10)
    sleep_s = st.number_input("Sleep between downloads (sec)", min_value=0.0, value=0.3, step=0.1)
    retries = st.slider("Max retries per ticker", 0, 5, 2)
    days = st.slider("Lookback period (days)", 90, 365, 180)
    export_filename = st.text_input("Export base filename", "sp500_scan_v35")

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

@st.cache_data(show_spinner=False)
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
    return pd.DataFrame()

# -----------------------------
# Main
# -----------------------------
universe = EMBEDDED_SP500.copy()
if len(universe) > max_universe:
    universe = universe[: int(max_universe)]

rows = []
failures = []
progress = st.progress(0)
for idx, t in enumerate(universe, start=1):
    try:
        data = fetch_one(t, days, retries, sleep_s)
        if data.empty or len(data) < 60:
            continue

        close = data["Close"]
        vol = data["Volume"]

        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        c_last = float(close.iloc[-1])
        e20 = float(ema20.iloc[-1])
        e50 = float(ema50.iloc[-1])

        # Technical signals
        trend_ok = (e20 > e50) and (c_last > e20)
        macd_line, sig_line, hist = macd(close)
        m_last, s_last, h_last, h_prev = float(macd_line.iloc[-1]), float(sig_line.iloc[-1]), float(hist.iloc[-1]), float(hist.iloc[-2])
        macd_ok = (m_last > s_last) and (h_last > 0) and (h_last > h_prev)
        vol_avg20 = vol.rolling(20).mean()
        v_last, v_avg = float(vol.iloc[-1]), float(vol_avg20.iloc[-1])
        vol_ok = (v_last >= vol_mult * v_avg) if v_avg > 0 else False

        entry, stop = c_last, e50
        if stop > 0 and entry > stop:
            risk = entry - stop
            target = entry + rr_min * risk
            rr = (target - entry) / risk
            rr_ok = rr >= rr_min
        else:
            target, rr, rr_ok = None, None, False

        # Catalyst placeholder (simulate earnings proximity for demo)
        catalyst = False
        catalyst_reason = ""
        if "INTC" in t or "MU" in t:  # demo hook
            catalyst = True
            catalyst_reason = "Earnings"

        score = int(trend_ok) + int(macd_ok) + int(vol_ok) + int(rr_ok) + int(catalyst)
        status = "Pass"
        notes = ""

        if score >= 3:
            if score == 5:
                status, notes = "PRIME", "Clean TA + Catalyst"
            elif score == 4 and catalyst:
                status, notes = "Catalyst PRIME", "News-driven"
            elif score == 4 and not catalyst:
                status, notes = "Strong TA", "Clean technicals"
            elif score == 3:
                status, notes = "Candidate", "Early setup"

            rows.append({
                "Ticker": t,
                "Entry": round(entry, 2),
                "Stop(EMA50)": round(stop, 2) if stop else None,
                "Target": round(target, 2) if target else None,
                "R/R": round(rr, 2) if rr else None,
                "Score (0-5)": score,
                "Status": status,
                "Catalyst": catalyst_reason if catalyst else "—",
                "Notes": notes,
            })
    except Exception as e:
        failures.append((t, str(e)))
    if idx % 5 == 0 or idx == len(universe):
        progress.progress(idx / len(universe))

# -----------------------------
# Output
# -----------------------------
if rows:
    df = pd.DataFrame(rows).sort_values(["Score (0-5)","Status"], ascending=[False, True])
    st.subheader("Results")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name=f"{export_filename}.csv", mime="text/csv")
else:
    st.warning("No candidates found.")

if failures:
    with st.expander("Fetch errors"):
        for t, msg in failures:
            st.write(f"- {t}: {msg}")
