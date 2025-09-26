
import time
import math
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

APP_NAME = "📈 S&P 500 Next‑Day Rise Scanner (Streamlit)"
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("Scans the S&P 500 and surfaces names most likely to rise tomorrow using simple, robust signals: Trend, MACD momentum, and Volume accumulation.")

# -----------------------------
# Settings
# -----------------------------
with st.sidebar:
    st.subheader("Settings")
    vol_mult = st.number_input("Volume multiple (vs 20‑day avg) ≥", min_value=1.0, value=1.3, step=0.1)
    rr_min = st.number_input("Min Risk/Reward", min_value=1.0, value=2.0, step=0.5)
    max_universe = st.number_input("Max tickers to scan (set 505 for full S&P)", min_value=50, value=250, step=25)
    sleep_s = st.number_input("Sleep between downloads (sec)", min_value=0.0, value=0.4, step=0.1)
    retries = st.slider("Max retries per ticker", 0, 5, 2)
    days = st.slider("Lookback period (days)", 90, 365, 180)
    show_only_primes = st.checkbox("Show only PRIME (score = 4)", value=False)
    export_filename = st.text_input("Export base filename", "sp500_nextday_scan")

# -----------------------------
# Utilities
# -----------------------------
@st.cache_data(show_spinner=False)
def load_sp500_fallback():
    try:
        # Try to fetch from Wikipedia live (may fail in some environments)
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = tables[0]
        tickers = df["Symbol"].tolist()
        # Normalize BRK.B and BF.B style tickers for Yahoo
        tickers = [t.replace(".", "-") for t in tickers]
        return tickers
    except Exception:
        # Fallback to bundled CSV
        df = pd.read_csv("sp500_tickers_fallback.csv")
        tickers = df["Symbol"].tolist()
        tickers = [t.replace(".", "-") for t in tickers]
        return tickers

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
    raise RuntimeError(f"{ticker}: {last_err}")

# -----------------------------
# Main
# -----------------------------
universe = load_sp500_fallback()
if len(universe) > max_universe:
    universe = universe[: int(max_universe)]

st.info(f"Scanning {len(universe)} tickers... (adjust in the sidebar)")

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
        trend_ok = bool(ema20.iloc[-1] > ema50.iloc[-1] and close.iloc[-1] > ema20.iloc[-1])

        # MACD momentum
        macd_line, sig_line, hist = macd(close)
        macd_ok = bool(
            macd_line.iloc[-1] > sig_line.iloc[-1] and
            hist.iloc[-1] > 0 and
            hist.iloc[-1] > hist.iloc[-2]  # momentum improving
        )

        # Volume accumulation
        vol_avg20 = vol.rolling(20).mean()
        vol_ok = bool(vol.iloc[-1] >= vol_mult * vol_avg20.iloc[-1])

        # Simple R/R check (stop at EMA50, target = entry + rr_min * (entry - stop))
        entry = float(close.iloc[-1])
        stop = float(ema50.iloc[-1])
        if stop <= 0 or entry <= stop:
            rr_ok = False
            target = None
            rr = None
            risk = None
        else:
            risk = entry - stop
            target = entry + rr_min * risk
            rr = (target - entry) / risk
            rr_ok = rr >= rr_min

        # Scoring (4 = PRIME)
        score = int(trend_ok) + int(macd_ok) + int(vol_ok) + int(rr_ok)
        status = "PRIME" if score == 4 else ("Candidate" if score >= 3 else "Pass")

        if (show_only_primes and status == "PRIME") or (not show_only_primes and score >= 3):
            rows.append({
                "Ticker": t,
                "Entry": round(entry, 2),
                "Stop(EMA50)": round(stop, 2) if stop else None,
                "Target": round(target, 2) if target else None,
                "R/R": round(rr, 2) if rr else None,
                "TrendOK": trend_ok,
                "MACD_OK": macd_ok,
                "VolOK": vol_ok,
                "Score(0-4)": score,
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
    df = pd.DataFrame(rows).sort_values(["Status","Score(0-4)","R/R"], ascending=[True, False, False])
    st.subheader("Results")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name=f"{export_filename}.csv", mime="text/csv")

    try:
        with pd.ExcelWriter(f"{export_filename}.xlsx", engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="results")
        with open(f"{export_filename}.xlsx", "rb") as f:
            st.download_button("⬇️ Download Excel", data=f, file_name=f"{export_filename}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception:
        st.info("Install xlsxwriter to enable Excel export.")
else:
    st.warning("No PRIME/Candidate tickers found with current thresholds. Try lowering volume multiple or min R/R.")

if failures:
    with st.expander("Show fetch warnings/errors"):
        for t, msg in failures:
            st.write(f"- {t}: {msg}")
