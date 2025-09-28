import time
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

APP_NAME = "📈 S&P 500 Scanner v3.7 — Autostart (MACD‑V + Badges)"
st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(APP_NAME)
st.caption("Autostarts on load. MACD‑V only. Adds ✅/⚠️/❌ badges and sorts best→worst.")

# Sidebar
with st.sidebar:
    st.subheader("Controls")
    vol_mult = st.number_input("Volume multiple (vs 20‑day avg) ≥", min_value=1.0, value=1.3, step=0.1)
    rr_min = st.number_input("Min Risk/Reward", min_value=1.0, value=2.0, step=0.5)
    max_universe = st.number_input("Max tickers to scan", min_value=50, value=500, step=50)
    sleep_s = st.number_input("Sleep between downloads (sec)", min_value=0.0, value=0.3, step=0.1)
    retries = st.slider("Max retries per ticker", 0, 5, 2)
    days = st.slider("Lookback period (days)", 90, 365, 180)
    export_filename = st.text_input("Export base filename", "sp500_scan_v37_macdv_badges")

# Indicators (MACD‑V only)
def vwema(price: pd.Series, volume: pd.Series, span: int) -> pd.Series:
    vp = (price * volume).ewm(span=span, adjust=False).mean()
    v = volume.ewm(span=span, adjust=False).mean().replace(0, np.nan)
    return vp / v

def macd_v(price: pd.Series, volume: pd.Series, fast=12, slow=26, signal=9):
    vw_fast = vwema(price, volume, fast)
    vw_slow = vwema(price, volume, slow)
    macd_line = vw_fast - vw_slow
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

# Universe (Wikipedia with fallback)
EMBEDDED_SP500 = [
"AAPL","MSFT","GOOGL","AMZN","META","NVDA","BRK-B","UNH","XOM","LLY","JPM","V","MA","HD","PG","COST","JNJ","MRK","PEP","KO",
"BAC","ADBE","WMT","NFLX","CRM","TMO","AVGO","CVX","LIN","TXN","PFE","ABT","CSCO","ACN","AMD","MCD","DHR","INTC","INTU","QCOM",
"LOW","AMGN","PM","HON","AMAT","BMY","IBM","GE","GS","CAT","NOW","BA","ISRG","BKNG","MDT","RTX","BLK","SPGI","PLD","DE","AMT",
"SYK","LMT","SCHW","MS","ADI","GILD","MU","ETN","ONTO","IONQ","ORCL","TSLA","PYPL","SHOP","NKE","SBUX","T","VZ","C","USB","FDX",
"UPS","MAR","DG","A","ALB","ALGN","ALNY","AEP","AIG","AON","APA","APD","APH","ARE","ATO","AXP","AZO","BALL","BIIB","BK","BKR",
"BMY","CHTR","CL","CLX","CMCSA","CMG","COF","COP","CPRT","CSX","CTAS","CTSH","CVS","D","DAL","DD","DLR","DOW","DUK","EA","EBAY",
"ECL","ED","EFX","EIX","EL","EMR","EOG","EQIX","EQR","EQT","ESS","ETSY","EXC","F","FAST","FCX","FIS","FISV","FITB","FTNT","GD",
"GPN","HCA","HES","HIG","HLT","HOLX","HPQ","ICE","ILMN","INTU","IP","IT","JNPR","KHC","KMI","KMX","KO","LEN","LHX","LRCX","LULU",
"LYB","MAR","MKC","MMC","MNST","MO","MRNA","MSI","NEM","NOC","NOW","NTRS","NVDA","NVR","NWSA","ODFL","OKE","ORLY","OTIS","PANW",
"PAYC","PCAR","PDD","PEP","PGR","PLD","PM","PNC","PNR","PWR","PYPL","QRVO","REGN","ROK","ROL","ROST","RSG","SBAC","SHW","SIRI",
"SLB","SNPS","SO","SPG","SRE","STT","STZ","SWK","SYF","TDG","TEL","TGT","TJX","TMO","TRV","TSCO","TT","TTWO","TXN","TXT","UAL",
"UBER","UNH","UNP","UPS","USB","VFC","VLO","VMC","VRSK","VRTX","VTR","WAB","WBA","WEC","WELL","WFC","WM","WMB","WMT","ZBH","ZTS"
]

@st.cache_data(show_spinner=True)
def load_sp500_symbols():
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = tables[0]
        syms = df["Symbol"].astype(str).str.upper().str.replace(".", "-", regex=False).tolist()
        seen, out = set(), []
        for s in syms:
            if s not in seen:
                seen.add(s); out.append(s)
        if len(out) >= 400:
            return out
    except Exception:
        pass
    return EMBEDDED_SP500

symbols = load_sp500_symbols()
if len(symbols) > max_universe:
    symbols = symbols[: int(max_universe)]

# Scan on load
st.info(f"Scanning {len(symbols)} tickers… (MACD‑V only)")
rows, failures = [], []
progress = st.progress(0)
status_box = st.empty()

def macdv_badge(hist_series):
    # Badge + weight for sorting
    if len(hist_series) < 2:
        return "⚠️ Weak/Flat", 1
    last = float(hist_series.iloc[-1])
    prev = float(hist_series.iloc[-2])
    if last > 0 and last > prev:
        return "✅ Bullish", 2
    if last < 0:
        return "❌ Bearish", 0
    return "⚠️ Weak/Flat", 1

for idx, t in enumerate(symbols, start=1):
    try:
        data = fetch_one(t, days, retries, sleep_s)
        if data.empty or len(data) < 60:
            continue

        close = data["Close"]
        vol = data["Volume"].fillna(0)

        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        c_last = float(close.iloc[-1])
        e20, e50 = float(ema20.iloc[-1]), float(ema50.iloc[-1])
        trend_ok = (e20 > e50) and (c_last > e20)

        _, _, hist_v = macd_v(close, vol)
        m_note, m_weight = macdv_badge(hist_v)

        m_last = float(hist_v.iloc[-1])
        m_prev = float(hist_v.iloc[-2]) if len(hist_v) >= 2 else m_last
        macd_ok = (m_last > 0) and (m_last > m_prev)

        vol_avg20 = vol.rolling(20).mean()
        v_last, v_avg = float(vol.iloc[-1]), float(vol_avg20.iloc[-1])
        vol_ok = (v_avg > 0) and (v_last >= vol_mult * v_avg)

        entry, stop = c_last, e50
        if stop > 0 and entry > stop:
            risk = entry - stop
            target = entry + rr_min * risk
            rr = (target - entry) / risk
            rr_ok = rr >= rr_min
        else:
            target, rr, rr_ok = None, None, False

        catalyst = False  # placeholder
        score = int(trend_ok) + int(macd_ok) + int(vol_ok) + int(rr_ok) + int(catalyst)

        if score >= 0:  # keep all, you asked to see losers too
            status = ("PRIME" if score == 5 else
                      ("Strong TA" if score == 4 else
                       ("Candidate" if score == 3 else "Weak/Skip")))

            rows.append({
                "Ticker": t,
                "Entry": round(entry, 2),
                "Stop(EMA50)": round(stop, 2) if stop else None,
                "Target": round(target, 2) if target else None,
                "R/R": round(rr, 2) if rr else None,
                "Score (0-5)": score,
                "Status": status,
                "MACD‑V": m_note,
                "_MACD_Weight": m_weight
            })
    except Exception as e:
        failures.append((t, str(e)))
    if idx % 10 == 0 or idx == len(symbols):
        progress.progress(idx / len(symbols))
        status_box.info(f"Scanning {idx}/{len(symbols)}…")

# Output
if rows:
    df = pd.DataFrame(rows)
    # Sort: Score desc → Status → R/R desc → MACD‑V badge weight desc
    df = df.sort_values(["Score (0-5)", "Status", "R/R", "_MACD_Weight"],
                        ascending=[False, True, False, False]).drop(columns=["_MACD_Weight"])
    st.subheader("Results")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name=f"{export_filename}.csv", mime="text/csv")
else:
    st.warning("No candidates found. Try adjusting thresholds/universe.")

if failures:
    with st.expander("Fetch errors"):
        for t, msg in failures:
            st.write(f"- {t}: {msg}")
