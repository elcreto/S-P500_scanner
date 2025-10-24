#!/usr/bin/env python3
# Headless exporter for S-P500_scanner
# - Runs streamlit_app logic
# - Finds the ranked dataframe with a real Score column
# - Writes /app/data/scan_cli.csv used by the server cron

import os, re, sys
import pandas as pd
import streamlit_app as app

def _flat(cols):
    out=[]
    for c in cols:
        out.append(" / ".join(map(str,c)) if isinstance(c, tuple) else str(c))
    return out

def _pick(ns):
    # Prefer a DataFrame named df that already represents the ranked/post-gate result
    df = ns.get("df")
    if isinstance(df, pd.DataFrame) and not df.empty:
        d = df.copy(); d.columns = _flat(d.columns)
        if any(str(c).lower().startswith("score") for c in d.columns):
            return d
    # Fallback: scan all DFs and choose the most likely ranked one
    cands=[]
    for name, obj in ns.items():
        if isinstance(obj, pd.DataFrame) and len(obj)>0:
            d = obj.copy(); d.columns = _flat(d.columns)
            cols = [str(c).lower() for c in d.columns]
            if any(c.startswith("score") for c in cols):
                pr = 0; n = name.lower()
                if name == "df": pr += 100
                if "rank" in n: pr += 10
                if "post" in n: pr += 6
                if "all" in n or "pre" in n: pr -= 5
                cands.append((pr, name, d))
    if not cands:
        sys.exit("❌ No ranked DataFrame with a Score column found")
    cands.sort(key=lambda t: t[0], reverse=True)
    return cands[0][2]

# Tell the app we’re in headless/CLI mode (if it cares)
os.environ["BOT_CLI"] = "1"

ranked = _pick(vars(app)).copy()

# Normalize columns
sc = next((c for c in ranked.columns if str(c).lower().startswith("score")), None)
if sc and sc != "Score":
    ranked.rename(columns={sc: "Score"}, inplace=True)

sym = next((c for c in ranked.columns if str(c).lower() in ("ticker","symbol")), None)
if sym and sym != "Ticker":
    ranked.rename(columns={sym: "Ticker"}, inplace=True)

# Put key columns first, keep the rest for inspection
front = [c for c in ("Ticker","Score","Source") if c in ranked.columns]
rest  = [c for c in ranked.columns if c not in front]
ranked = ranked[front + rest]

out = "/app/data/scan_cli.csv"
os.makedirs("/app/data", exist_ok=True)
ranked.to_csv(out, index=False)
print(f"✅ wrote {len(ranked)} ranked rows to {out}")
