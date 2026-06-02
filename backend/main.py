
import os
import re
import json
import time
import joblib
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from functools import lru_cache
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load model + data ──────────────────────────────────────────────
BASE = os.path.dirname(__file__)

@lru_cache(maxsize=1)
def load_model():
    modelo = joblib.load(os.path.join(BASE, "modelo_ufc_v3.pkl"))
    features = joblib.load(os.path.join(BASE, "features_v3.pkl"))
    return modelo, features

@lru_cache(maxsize=1)
def load_df():
    df = pd.read_csv(os.path.join(BASE, "ufc_master_clean.csv"))
    df["R_lower"] = df["R_fighter"].str.lower()
    df["B_lower"] = df["B_fighter"].str.lower()
    return df

# ── Helpers ────────────────────────────────────────────────────────
def fix_name(name):
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", name)

def safe_float(val, default=0.0):
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except:
        return default

# Odds cache
_odds_cache = {}
_odds_ts = 0

def get_odds_map():
    global _odds_cache, _odds_ts
    if _odds_cache and (time.time() - _odds_ts) < 3600:
        return _odds_cache
    key = os.environ.get("ODDS_API_KEY", "")
    if not key:
        return {}
    try:
        resp = requests.get(
            "https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds",
            params={"apiKey": key, "regions": "us", "markets": "h2h", "oddsFormat": "american"},
            timeout=10
        )
        if resp.status_code != 200:
            return {}
        totals = {}; counts = {}
        for fight in resp.json():
            for book in fight.get("bookmakers", []):
                for market in book.get("markets", []):
                    if market.get("key") == "h2h":
                        for o in market.get("outcomes", []):
                            n = o["name"].lower()
                            totals[n] = totals.get(n, 0) + o["price"]
                            counts[n] = counts.get(n, 0) + 1
        _odds_cache = {n: round(totals[n]/counts[n]) for n in totals}
        _odds_ts = time.time()
        return _odds_cache
    except:
        return {}

def predict(nome_r, nome_b):
    modelo, features = load_model()
    df = load_df()
    odds_map = get_odds_map()

    def get_row(nome):
        lr = df[df["R_lower"] == nome.lower()]
        lr2 = df[df["B_lower"] == nome.lower()]
        if len(lr) > 0:
            return lr.sort_values("date", ascending=False).iloc[0], "R_"
        elif len(lr2) > 0:
            return lr2.sort_values("date", ascending=False).iloc[0], "B_"
        return None, None

    sr, pr = get_row(nome_r)
    sb, pb = get_row(nome_b)
    if sr is None or sb is None:
        return None

    def v(row, p, col):
        return safe_float(row.get(f"{p}{col}", 0))

    r_odds = odds_map.get(nome_r.lower()) or v(sr, pr, "odds")
    b_odds = odds_map.get(nome_b.lower()) or v(sb, pb, "odds")

    row = pd.DataFrame([[
        v(sr,pr,"current_win_streak"), v(sb,pb,"current_win_streak"),
        v(sr,pr,"current_lose_streak"), v(sb,pb,"current_lose_streak"),
        v(sr,pr,"longest_win_streak"), v(sb,pb,"longest_win_streak"),
        v(sr,pr,"wins"), v(sb,pb,"wins"),
        v(sr,pr,"losses"), v(sb,pb,"losses"),
        v(sr,pr,"avg_SIG_STR_pct"), v(sb,pb,"avg_SIG_STR_pct"),
        v(sr,pr,"avg_TD_pct"), v(sb,pb,"avg_TD_pct"),
        v(sr,pr,"avg_SUB_ATT"), v(sb,pb,"avg_SUB_ATT"),
        v(sr,pr,"Height_cms"), v(sb,pb,"Height_cms"),
        v(sr,pr,"Reach_cms"), v(sb,pb,"Reach_cms"),
        v(sr,pr,"age"), v(sb,pb,"age"),
        v(sr,pr,"Reach_cms") - v(sb,pb,"Reach_cms"),
        v(sr,pr,"age") - v(sb,pb,"age"),
        v(sr,pr,"current_win_streak") - v(sb,pb,"current_win_streak"),
        v(sr,pr,"avg_SIG_STR_pct") - v(sb,pb,"avg_SIG_STR_pct"),
        v(sr,pr,"match_weightclass_rank"), v(sb,pb,"match_weightclass_rank"),
        r_odds, b_odds,
    ]], columns=features)

    if isinstance(modelo, tuple):
        rf, lr2 = modelo
        prob = rf.predict_proba(row)[0] * 0.7 + lr2.predict_proba(row)[0] * 0.3
    else:
        prob = modelo.predict_proba(row)[0]

    prob_r = round(float(prob[1]) * 100, 1)
    prob_b = round(float(prob[0]) * 100, 1)
    winner = nome_r if prob_r >= prob_b else nome_b
    conf = "High" if max(prob_r,prob_b) >= 70 else "Medium" if max(prob_r,prob_b) >= 58 else "Toss-up"

    market_fav = None
    if r_odds and b_odds:
        market_fav = nome_r if r_odds < b_odds else nome_b

    def implied(o):
        if not o: return None
        return round((abs(o)/(abs(o)+100))*100 if o < 0 else (100/(o+100))*100, 1)

    return {
        "winner": winner,
        "prob_r": prob_r,
        "prob_b": prob_b,
        "confidence": conf,
        "r_odds": r_odds,
        "b_odds": b_odds,
        "r_implied": implied(r_odds),
        "b_implied": implied(b_odds),
        "market_fav": market_fav,
        "agrees_market": market_fav == winner if market_fav else None,
    }

# ── Sherdog scrapers ───────────────────────────────────────────────
_events_cache = {}
_events_ts = 0

def scrape_events():
    global _events_cache, _events_ts
    if _events_cache and (time.time() - _events_ts) < 3600:
        return _events_cache
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get("https://www.sherdog.com/organizations/Ultimate-Fighting-Championship-UFC-2", headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        tabelas = soup.find_all("table", class_="new_table event")
        if not tabelas:
            return {}
        eventos = []
        for row in tabelas[0].find_all("tr")[1:]:
            cols = row.find_all("td")
            link = row.find("a")
            if link and cols:
                href = f"https://www.sherdog.com{link.get('href','')}"
                eventos.append({
                    "name": link.text.strip(),
                    "date": cols[1].text.strip() if len(cols)>1 else "",
                    "location": cols[2].text.strip() if len(cols)>2 else "",
                    "url": href,
                })
        _events_cache = eventos
        _events_ts = time.time()
        return eventos
    except:
        return []

def scrape_card(event_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    fights = []
    try:
        resp = requests.get(event_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        fc = soup.find("div", class_="fight_card")
        if fc:
            l = fc.find("div", class_="left_side")
            r = fc.find("div", class_="right_side")
            if l and r:
                ln = l.find("h3"); rn = r.find("h3")
                ll = l.find("a"); rl = r.find("a")
                if ln and rn:
                    fights.append({
                        "R_fighter": fix_name(ln.text.strip()),
                        "B_fighter": fix_name(rn.text.strip()),
                        "R_link": f"https://www.sherdog.com{ll.get('href','')}" if ll else "",
                        "B_link": f"https://www.sherdog.com{rl.get('href','')}" if rl else "",
                        "title_bout": "title" in fc.text.lower(),
                        "is_main": True,
                    })
        tabela = soup.find("table", class_="new_table upcoming")
        if tabela:
            for row in tabela.find_all("tr")[1:]:
                cells = []
                for col in row.find_all("td"):
                    lnk = col.find("a")
                    if lnk and lnk.text.strip():
                        cells.append({"name": fix_name(lnk.text.strip()), "href": f"https://www.sherdog.com{lnk.get('href','')}"})
                if len(cells) >= 2:
                    fights.append({
                        "R_fighter": cells[0]["name"],
                        "B_fighter": cells[1]["name"],
                        "R_link": cells[0]["href"],
                        "B_link": cells[1]["href"],
                        "title_bout": False,
                        "is_main": False,
                    })
    except:
        pass
    return fights

def scrape_fighter_profile(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        profile = {}
        nt = soup.find("span", class_="fn")
        profile["name"] = nt.text.strip() if nt else ""
        height = reach = age = ""
        for bio in soup.find_all("div", class_="bio-holder"):
            t = bio.text
            if "HEIGHT" in t:
                m = re.search(r"([\d.]+)\s*cm", t)
                if m: height = m.group(1)
            if "REACH" in t:
                m = re.search(r"REACH[^\d]*([\d.]+)\s*cm", t)
                if m: reach = m.group(1)
            if "AGE" in t:
                m = re.search(r"AGE\s*(\d+)", t)
                if m: age = m.group(1)
        profile["height_cm"] = height
        profile["reach_cm"] = reach
        profile["age"] = age
        wc = ""
        cd = soup.find("div", class_="association-class")
        if cd and "CLASS" in cd.text:
            wc = cd.text.split("CLASS")[-1].strip().split("\n")[0].strip()
        profile["weight_class"] = wc
        fights = []
        tab = soup.find("table", class_="new_table fighter")
        if tab:
            for row in tab.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 5:
                    ol = cols[1].find("a")
                    dm = re.search(r"([A-Z][a-z]{2}\s*/?\s*\d{1,2}\s*/?\s*\d{4})", cols[2].text)
                    fights.append({
                        "result": cols[0].text.strip().lower(),
                        "opponent": fix_name(ol.text.strip()) if ol else cols[1].text.strip(),
                        "date": dm.group(1) if dm else "",
                        "method": cols[3].text.strip()[:40],
                        "round": cols[4].text.strip(),
                    })
        profile["fights"] = fights
        profile["wins"] = sum(1 for f in fights if f["result"]=="win")
        profile["losses"] = sum(1 for f in fights if f["result"]=="loss")
        def cat(m):
            ml = m.lower()
            if "ko" in ml or "tko" in ml: return "KO/TKO"
            if "sub" in ml: return "Submission"
            if "dec" in ml: return "Decision"
            return "Other"
        wins = [f for f in fights if f["result"]=="win"]
        losses = [f for f in fights if f["result"]=="loss"]
        tags = []; insights = []
        stopped = [f for f in losses if cat(f["method"]) in ("KO/TKO","Submission")]
        if losses and not stopped:
            tags.append("Never been finished")
            insights.append(f"Has never been stopped — all {len(losses)} losses came by decision.")
        wf = [f for f in wins if cat(f["method"]) in ("KO/TKO","Submission")]
        if wins:
            rate = round(len(wf)/len(wins)*100)
            if rate >= 70:
                tags.append("Finisher")
                insights.append(f"Finishes {rate}% of wins — {len(wf)} of {len(wins)} inside the distance.")
        r1 = [f for f in wf if str(f["round"]).strip()=="1"]
        if len(wf) >= 3 and len(r1)/len(wf) >= 0.5:
            tags.append("Fast starter")
            insights.append(f"{len(r1)} of {len(wf)} finishes came in round 1.")
        if wins:
            mc = {}
            for f in wins:
                c = cat(f["method"]); mc[c] = mc.get(c,0)+1
            tm,tc = max(mc.items(), key=lambda x:x[1])
            if tc/len(wins) >= 0.6:
                if tm=="Submission": tags.append("Submission specialist"); insights.append(f"{tc} of {len(wins)} wins by submission.")
                elif tm=="KO/TKO": tags.append("Knockout artist"); insights.append(f"{tc} of {len(wins)} wins by KO/TKO.")
                elif tm=="Decision": tags.append("Volume grinder"); insights.append(f"{tc} of {len(wins)} wins by decision.")
        deep = [f for f in fights if str(f["round"]).strip() in ("3","4","5")]
        if len(deep) >= 3:
            dw = sum(1 for f in deep if f["result"]=="win"); dr = dw/len(deep)
            if dr <= 0.34: tags.append("Fades late"); insights.append(f"Just {dw}-{len(deep)-dw} in fights reaching round 3.")
            elif dr >= 0.8: tags.append("Strong late"); insights.append(f"{dw}-{len(deep)-dw} in fights reaching round 3 — gets stronger late.")
        streak = 0; stp = fights[0]["result"] if fights else ""
        for f in fights:
            if f["result"]==stp: streak+=1
            else: break
        if stp=="win" and streak>=4: tags.append(f"{streak}-fight win streak"); insights.append(f"Riding a {streak}-fight win streak.")
        elif stp=="loss" and streak>=2: tags.append("Skid"); insights.append(f"On a {streak}-fight losing skid.")
        if len(fights)>=30: tags.append("Veteran"); insights.append(f"Deep experience — {len(fights)} pro fights.")
        profile["tags"] = tags
        profile["insights"] = insights
        return profile
    except Exception as e:
        return {"error": str(e)}

# ── Endpoints ──────────────────────────────────────────────────────
@app.get("/events")
def get_events():
    return scrape_events()

@app.get("/events/{event_idx}/card")
def get_card(event_idx: int):
    events = scrape_events()
    if event_idx >= len(events):
        return {"error": "Event not found"}
    event = events[event_idx]
    fights = scrape_card(event["url"])
    predictions = []
    for f in fights:
        pred = predict(f["R_fighter"], f["B_fighter"])
        predictions.append({**f, "prediction": pred})
    return {"event": event, "fights": predictions}

@app.get("/predict")
def get_prediction(fighter_r: str, fighter_b: str):
    return predict(fighter_r, fighter_b)

@app.get("/fighter")
def get_fighter(url: str):
    return scrape_fighter_profile(url)

@app.get("/fighter/search")
def search_fighter(name: str):
    df = load_df()
    mask = df["R_fighter"].str.lower().str.contains(name.lower()) | df["B_fighter"].str.lower().str.contains(name.lower())
    matches = set()
    for _, row in df[mask].iterrows():
        if name.lower() in row["R_fighter"].lower(): matches.add(row["R_fighter"])
        if name.lower() in row["B_fighter"].lower(): matches.add(row["B_fighter"])
    return {"results": sorted(list(matches))[:20]}

@app.get("/accuracy")
def get_accuracy():
    path = os.path.join(BASE, "accuracy_history.json")
    if not os.path.exists(path): return []
    with open(path) as f: return json.load(f)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def get_fighter_stats(name: str):
    df = load_df()
    mask_r = df["R_lower"] == name.lower()
    mask_b = df["B_lower"] == name.lower()
    if mask_r.any():
        row = df[mask_r].sort_values("date", ascending=False).iloc[0]
        p = "R_"
    elif mask_b.any():
        row = df[mask_b].sort_values("date", ascending=False).iloc[0]
        p = "B_"
    else:
        return {"error": "Fighter not found"}
    def g(col, default=0):
        try:
            v = row.get(f"{p}{col}", default)
            return round(float(v), 1) if not pd.isna(v) else default
        except:
            return default
    return {
        "name": name,
        "wins": int(g("wins")),
        "losses": int(g("losses")),
        "ko_wins": int(g("win_by_KO/TKO")),
        "sub_wins": int(g("win_by_Submission")),
        "dec_wins": int(g("win_by_Decision_Unanimous")),
        "win_streak": int(g("current_win_streak")),
        "sig_str_pct": g("avg_SIG_STR_pct"),
        "td_pct": g("avg_TD_pct"),
        "height_cm": g("Height_cms"),
        "reach_cm": g("Reach_cms"),
        "age": g("age"),
    }

@app.get("/fighters")
def list_fighters():
    df = load_df()
    all_fighters = sorted(list(set(df["R_fighter"].tolist() + df["B_fighter"].tolist())))
    return {"fighters": all_fighters}
