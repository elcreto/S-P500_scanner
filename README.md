
# S&P 500 Next‑Day Rise Scanner (Streamlit)

Scans the S&P 500 and surfaces names most likely to rise tomorrow using:
- Trend alignment (Close > EMA20 > EMA50)
- MACD momentum improvement (MACD > Signal and histogram rising)
- Volume accumulation (today's volume ≥ N × 20‑day average)
- Simple Risk/Reward sanity check (stop at EMA50; target = Entry + R×risk)

## Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Notes
- By default it will try to fetch the S&P 500 list from Wikipedia. If blocked, it falls back to `sp500_tickers_fallback.csv` (editable).
- Yahoo Finance rate limits are real. Use the sidebar to reduce universe size, increase sleep, or retries.
- Use the CSV/Excel export to save daily candidates.
