
# S&P 500 Next-Day Scanner v3.5 (Catalyst Aware)

Scoring system 0–5 with Catalyst Override.

## Signals
- Trend (EMA20 > EMA50, Close > EMA20)
- MACD momentum improving
- Volume ≥ N × 20-day average
- Risk/Reward ≥ threshold
- Catalyst (earnings, upgrades, contracts)

## Status Labels
- PRIME (5): All technicals + catalyst
- Strong TA (4): Pure technical
- Catalyst PRIME (3+1=4): 3 tech + catalyst
- Candidate (3): 3 tech only
- Pass (<3): ignored

## Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
