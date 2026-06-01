# UFC Analytics v2.1 - Sherdog events

import streamlit as st
import pandas as pd
import joblib
import numpy as np
import requests
import warnings
from groq import Groq
import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
warnings.filterwarnings("ignore")

# ============ RICH FIGHTER PROFILES ============
def parse_sherdog_date(date_str):
    if not date_str:
        return None
    cleaned = re.sub(r"\s*/\s*", " ", date_str).strip()
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(cleaned, fmt)
        except:
            continue
    return None

def categorize(method):
    m = method.lower()
    if "ko" in m or "tko" in m: return "KO/TKO"
    if "sub" in m: return "Submission"
    if "dec" in m: return "Decision"
    return "Other"

def scrape_full_profile(sherdog_url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(sherdog_url, headers=headers, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    profile = {"url": sherdog_url}
    name_tag = soup.find("span", class_="fn")
    profile["name"] = name_tag.text.strip() if name_tag else ""
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
    profile["height_cm"] = height; profile["reach_cm"] = reach; profile["age"] = age
    wc = ""
    cls_div = soup.find("div", class_="association-class")
    if cls_div and "CLASS" in cls_div.text:
        wc = cls_div.text.split("CLASS")[-1].strip().split("\n")[0].strip()
    profile["weight_class"] = wc
    fights = []
    tabela = soup.find("table", class_="new_table fighter")
    if tabela:
        for linha in tabela.find_all("tr")[1:]:
            cols = linha.find_all("td")
            if len(cols) >= 6:
                result = cols[0].text.strip().lower()
                opp_link = cols[1].find("a")
                opponent = fix_name(opp_link.text.strip()) if opp_link else cols[1].text.strip()
                event_cell = cols[2].text.strip()
                dm = re.search(r"([A-Z][a-z]{2}\s*/?\s*\d{1,2}\s*/?\s*\d{4})", event_cell)
                date = dm.group(1) if dm else ""
                fights.append({"result": result, "opponent": opponent, "date": date, "method": cols[3].text.strip()[:40], "round": cols[4].text.strip()})
    profile["fights"] = fights
    profile["total_fights"] = len(fights)
    profile["wins"] = sum(1 for f in fights if f["result"] == "win")
    profile["losses"] = sum(1 for f in fights if f["result"] == "loss")
    return profile

def gerar_insights(profile):
    fights = profile.get("fights", [])
    if not fights: return {"tags": [], "insights": []}
    wins = [f for f in fights if f["result"] == "win"]
    losses = [f for f in fights if f["result"] == "loss"]
    tags = []; insights = []
    stopped = [f for f in losses if categorize(f["method"]) in ("KO/TKO", "Submission")]
    if losses and not stopped:
        tags.append("Never been finished"); insights.append(f"Has never been stopped — all {len(losses)} losses came by decision.")
    wf2 = [f for f in wins if categorize(f["method"]) in ("KO/TKO", "Submission")]
    if wins:
        rate = round(len(wf2)/len(wins)*100)
        if rate >= 70:
            tags.append("Finisher"); insights.append(f"Finishes {rate}% of his wins — {len(wf2)} of {len(wins)} inside the distance.")
    r1 = [f for f in wf2 if str(f["round"]).strip() == "1"]
    if len(wf2) >= 3 and len(r1)/len(wf2) >= 0.5:
        tags.append("Fast starter"); insights.append(f"{len(r1)} of his {len(wf2)} finishes came in round 1.")
    if wins:
        mc = {}
        for f in wins:
            c = categorize(f["method"]); mc[c] = mc.get(c, 0)+1
        tm, tc = max(mc.items(), key=lambda x: x[1])
        if tc/len(wins) >= 0.6:
            if tm == "Submission": tags.append("Submission specialist"); insights.append(f"{tc} of {len(wins)} wins by submission — a true grappling threat.")
            elif tm == "KO/TKO": tags.append("Knockout artist"); insights.append(f"{tc} of {len(wins)} wins by KO/TKO — serious power.")
            elif tm == "Decision": tags.append("Volume grinder"); insights.append(f"{tc} of {len(wins)} wins by decision — wins on output, not power.")
    deep = [f for f in fights if str(f["round"]).strip() in ("3","4","5")]
    if len(deep) >= 3:
        dw = sum(1 for f in deep if f["result"] == "win"); dr = dw/len(deep)
        if dr <= 0.34: tags.append("Fades late"); insights.append(f"Just {dw}-{len(deep)-dw} in fights reaching round 3 — a cardio question.")
        elif dr >= 0.8: tags.append("Strong late"); insights.append(f"{dw}-{len(deep)-dw} in fights that reach round 3 — gets stronger late.")
    streak = 0; stp = fights[0]["result"]
    for f in fights:
        if f["result"] == stp: streak += 1
        else: break
    if stp == "win" and streak >= 4: tags.append(f"{streak}-fight win streak"); insights.append(f"Riding a {streak}-fight win streak — peak form.")
    elif stp == "loss" and streak >= 2: tags.append("Skid"); insights.append(f"On a {streak}-fight losing skid.")
    ld = parse_sherdog_date(fights[0]["date"])
    if ld:
        days = (datetime.now() - ld).days
        if days > 1825: pass
        elif days > 730: tags.append("Long layoff"); insights.append(f"Hasn't fought in over {days//365} years — ring rust is a real factor.")
        elif days > 540: tags.append("Long layoff"); insights.append(f"Hasn't fought in {round(days/30)} months — ring rust is a real factor.")
        elif days < 90: tags.append("Active")
    if len(fights) >= 30: tags.append("Veteran"); insights.append(f"Deep experience — {len(fights)} pro fights.")
    return {"tags": tags, "insights": insights}



st.set_page_config(
    page_title="UFC Analytics",
    page_icon="🥊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dark theme CSS
st.markdown("""
<style>
    .stApp { background-color: #0a0a0a; color: #ffffff; }
    .stApp > header { background-color: #111111; }
    section[data-testid="stSidebar"] { background-color: #111111; }
    .stSelectbox > div > div { background-color: #1a1a1a; color: #fff; border: 1px solid #2a2a2a; }
    .stTextInput > div > div > input { background-color: #1a1a1a; color: #fff; border: 1px solid #2a2a2a; }
    .stButton > button { background-color: #E24B4A; color: white; border: none; border-radius: 8px; font-weight: 600; }
    .stButton > button:hover { background-color: #c43a39; border: none; }
    .stProgress > div > div { background-color: #1a1a1a; }
    div[data-testid="metric-container"] { background-color: #111; border: 1px solid #1e1e1e; border-radius: 8px; padding: 12px; }
    .stTabs [data-baseweb="tab-list"] { background-color: #111; border-bottom: 1px solid #222; }
    .stTabs [data-baseweb="tab"] { color: #888; }
    .stTabs [aria-selected="true"] { color: #fff; border-bottom: 2px solid #E24B4A; }
    .stExpander { background-color: #111; border: 1px solid #1e1e1e; border-radius: 12px; }
    .stDivider { border-color: #1e1e1e; }
    h1, h2, h3 { color: #ffffff; }
    p, label { color: #888; }
    .fight-card { background: #111; border: 1px solid #1e1e1e; border-radius: 12px; padding: 16px; margin-bottom: 10px; }
    .fight-card-featured { background: #111; border: 1px solid #E24B4A44; border-radius: 12px; padding: 16px; margin-bottom: 10px; }
    .fighter-name-r { color: #E24B4A; font-weight: 600; font-size: 15px; }
    .fighter-name-b { color: #378ADD; font-weight: 600; font-size: 15px; }
    .record-text { color: #555; font-size: 12px; }
    .pick-badge-r { background: #E24B4A22; color: #E24B4A; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .pick-badge-b { background: #378ADD22; color: #378ADD; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .conf-high { background: #27500A22; color: #639922; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
    .conf-med { background: #63380622; color: #BA7517; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
    .conf-low { background: #1e1e1e; color: #555; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
    .title-badge { background: #E24B4A22; color: #E24B4A; padding: 2px 8px; border-radius: 4px; font-size: 11px; display: inline-block; margin-bottom: 8px; }
    .stat-bar-r { background: #E24B4A; height: 4px; border-radius: 2px; }
    .stat-bar-b { background: #378ADD; height: 4px; border-radius: 2px; }
    .tag { background: #1a1a1a; color: #888; padding: 2px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #2a2a2a; display: inline-block; margin: 2px; }
    .section-title { font-size: 11px; font-weight: 600; color: #444; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 14px; }
    .form-dot-w { display: inline-block; width: 20px; height: 20px; border-radius: 50%; background: #27500A44; color: #639922; font-size: 10px; font-weight: 700; text-align: center; line-height: 20px; margin: 1px; }
    .form-dot-l { display: inline-block; width: 20px; height: 20px; border-radius: 50%; background: #7F1F1F44; color: #E24B4A; font-size: 10px; font-weight: 700; text-align: center; line-height: 20px; margin: 1px; }
</style>
""", unsafe_allow_html=True)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

@st.cache_data
def carregar_dados():
    df = pd.read_csv("ufc_master_clean.csv")
    modelo_obj = joblib.load("modelo_ufc_v3.pkl")
    features = joblib.load("features_v3.pkl")
    if isinstance(modelo_obj, tuple):
        modelo = modelo_obj
    else:
        modelo = modelo_obj
    todos = pd.concat([df["R_fighter"], df["B_fighter"]]).unique()
    lutadores = sorted(set([l.strip() for l in todos if isinstance(l, str)]))
    df["R_lower"] = df["R_fighter"].str.lower()
    df["B_lower"] = df["B_fighter"].str.lower()
    return df, modelo, features, lutadores

df, modelo, features, lutadores = carregar_dados()

def fix_name(name):
    import re
    return re.sub(r'([a-z])([A-Z])', r'\1 \2', name)

def buscar_card_sherdog(event_url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(event_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        lutas = []
        fight_card = soup.find("div", class_="fight_card")
        if fight_card:
            left = fight_card.find("div", class_="left_side")
            right = fight_card.find("div", class_="right_side")
            if left and right:
                r_name = left.find("h3")
                b_name = right.find("h3")
                r_link = left.find("a")
                b_link = right.find("a")
                if r_name and b_name:
                    lutas.append({
                        "R_fighter": fix_name(r_name.text.strip()),
                        "B_fighter": fix_name(b_name.text.strip()),
                        "R_link": f"https://www.sherdog.com{r_link.get('href', '')}" if r_link else "",
                        "B_link": f"https://www.sherdog.com{b_link.get('href', '')}" if b_link else "",
                        "title_bout": "title" in fight_card.text.lower()
                    })
        tabela = soup.find("table", class_="new_table upcoming")
        if tabela:
            for linha in tabela.find_all("tr")[1:]:
                fighter_cells = []
                for col in linha.find_all("td"):
                    lnk = col.find("a")
                    if lnk and lnk.text.strip():
                        fighter_cells.append({
                            "name": fix_name(lnk.text.strip()),
                            "href": f"https://www.sherdog.com{lnk.get('href', '')}"
                        })
                if len(fighter_cells) >= 2:
                    lutas.append({
                        "R_fighter": fighter_cells[0]["name"],
                        "B_fighter": fighter_cells[1]["name"],
                        "R_link": fighter_cells[0]["href"],
                        "B_link": fighter_cells[1]["href"],
                        "title_bout": False
                    })
        return lutas
    except:
        return []

@st.cache_data(ttl=3600)
def buscar_proximos_eventos():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        url = "https://www.sherdog.com/organizations/Ultimate-Fighting-Championship-UFC-2"
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        tabela = soup.find("table", class_="new_table event")
        if not tabela:
            return []
        eventos = []
        for linha in tabela.find_all("tr")[1:]:
            cols = linha.find_all("td")
            link = linha.find("a")
            if link and cols:
                nome = link.text.strip()
                href = f"https://www.sherdog.com{link.get('href', '')}"
                data = cols[1].text.strip() if len(cols) > 1 else ""
                local = cols[2].text.strip() if len(cols) > 2 else ""
                lutas = buscar_card_sherdog(href)
                if lutas:
                    eventos.append({"nome": nome, "data": data, "local": local, "url": href, "lutas": lutas})
        return eventos
    except:
        return []


def safe_float(val, default=0.0):
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except:
        return default

def safe_int(val, default=0):
    try:
        return int(val)
    except:
        return default

def buscar_lutador(nome):
    lutas_r = df[df["R_lower"] == nome.lower()]
    lutas_b = df[df["B_lower"] == nome.lower()]
    if len(lutas_r) > 0:
        stats = lutas_r.sort_values("date", ascending=False).iloc[0]
        p = "R_"
    elif len(lutas_b) > 0:
        stats = lutas_b.sort_values("date", ascending=False).iloc[0]
        p = "B_"
    else:
        return None
    return {
        "nome": nome.title(),
        "wins": safe_int(stats[f"{p}wins"]),
        "losses": safe_int(stats[f"{p}losses"]),
        "win_streak": safe_int(stats[f"{p}current_win_streak"]),
        "lose_streak": safe_int(stats[f"{p}current_lose_streak"]),
        "longest_win_streak": safe_int(stats[f"{p}longest_win_streak"]),
        "ko_wins": safe_int(stats[f"{p}win_by_KO/TKO"]),
        "sub_wins": safe_int(stats[f"{p}win_by_Submission"]),
        "dec_wins": safe_int(stats[f"{p}win_by_Decision_Unanimous"] + stats[f"{p}win_by_Decision_Split"] + stats[f"{p}win_by_Decision_Majority"]),
        "title_bouts": safe_int(stats[f"{p}total_title_bouts"]),
        "sig_str_pct": round(safe_float(stats[f"{p}avg_SIG_STR_pct"]) * 100, 1),
        "td_pct": round(safe_float(stats[f"{p}avg_TD_pct"]) * 100, 1),
        "sub_att": round(safe_float(stats[f"{p}avg_SUB_ATT"]), 1),
        "altura": f"{safe_float(stats[f'{p}Height_cms']):.0f} cm" if safe_float(stats[f"{p}Height_cms"]) > 0 else "N/A",
        "alcance": f"{safe_float(stats[f'{p}Reach_cms']):.0f} cm" if safe_float(stats[f"{p}Reach_cms"]) > 0 else "N/A",
        "peso": f"{safe_float(stats[f'{p}Weight_lbs']):.0f} lbs" if safe_float(stats[f"{p}Weight_lbs"]) > 0 else "N/A",
        "stance": str(stats[f"{p}Stance"]) if pd.notna(stats[f"{p}Stance"]) else "N/A",
        "idade": f"{safe_float(stats[f'{p}age']):.0f}" if safe_float(stats[f"{p}age"]) > 0 else "N/A",
    }

def ultimas_lutas(nome, n=3):
    lutas_r = df[df["R_lower"] == nome.lower()].copy()
    lutas_r["lado"] = "R"
    lutas_b = df[df["B_lower"] == nome.lower()].copy()
    lutas_b["lado"] = "B"
    todas = pd.concat([lutas_r, lutas_b])
    todas["data_dt"] = pd.to_datetime(todas["date"], errors="coerce")
    todas = todas.sort_values("data_dt", ascending=False).head(n)
    lutas = []
    for _, luta in todas.iterrows():
        lado = luta["lado"]
        adversario = luta["B_fighter"] if lado == "R" else luta["R_fighter"]
        winner = str(luta["Winner"]).strip()
        if winner == "Red":
            resultado = "W" if lado == "R" else "L"
        elif winner == "Blue":
            resultado = "W" if lado == "B" else "L"
        else:
            resultado = "D"
        lutas.append({
            "adversario": adversario,
            "data": luta["date"],
            "resultado": resultado,
            "metodo": str(luta["finish"]) if pd.notna(luta["finish"]) else "N/A",
            "round": luta["finish_round"],
        })
    return lutas

def resumo_performance(lutas):
    if not lutas:
        return "No recent data available."
    nv = sum(1 for l in lutas if l["resultado"] == "W")
    nd = sum(1 for l in lutas if l["resultado"] == "L")
    n = len(lutas)
    metodos = [l["metodo"] for l in lutas]
    fins = sum(1 for m in metodos if "KO" in str(m) or "Sub" in str(m) or "TKO" in str(m))
    if nv == n:
        if fins == n:
            return f"On fire — won all last {n} by finish. Dangerous at all times."
        elif fins > n // 2:
            return f"Strong form — {nv} wins in last {n}, mostly by finish."
        else:
            return f"Dominant — {nv} wins in last {n} fights by decision. High volume fighter."
    elif nv > nd:
        return f"Good form with {nv} win(s) in last {n} fights."
    elif nd == n:
        return f"Tough stretch — {nd} consecutive losses. Coming in under pressure."
    elif nd > nv:
        return f"Difficult run with {nd} loss(es) in last {n} fights."
    else:
        return f"Mixed results in last {n} fights. Unpredictable."

def gerar_tags(perfil):
    tags = []
    total = perfil["ko_wins"] + perfil["sub_wins"] + perfil["dec_wins"]
    if total > 0:
        if perfil["ko_wins"] / total > 0.4:
            tags.append("KO power")
        if perfil["sub_wins"] / total > 0.3:
            tags.append("Submission threat")
        if perfil["dec_wins"] / total > 0.5:
            tags.append("Decision fighter")
    if perfil["sig_str_pct"] >= 60:
        tags.append("Sharp striker")
    if perfil["td_pct"] >= 50:
        tags.append("Takedown efficient")
    if perfil["win_streak"] >= 3:
        tags.append("Hot streak")
    elif perfil["lose_streak"] >= 2:
        tags.append("Tough stretch")
    if perfil["title_bouts"] >= 3:
        tags.append("Championship experience")
    return tags

@st.cache_data(ttl=3600)
def buscar_odds_map(_v=3):
    key = st.secrets.get("ODDS_API_KEY", os.environ.get("ODDS_API_KEY", ""))
    if not key:
        return {"_error": "NO_KEY"}
    try:
        url = "https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds"
        params = {"apiKey": key, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return {"_error": f"HTTP_{resp.status_code}: {resp.text[:80]}"}
        data = resp.json()
        odds_map = {}
        for fight in data:
            totals = {}
            counts = {}
            for book in fight.get("bookmakers", []):
                for market in book.get("markets", []):
                    if market.get("key") == "h2h":
                        for o in market.get("outcomes", []):
                            n = o["name"].lower()
                            totals[n] = totals.get(n, 0) + o["price"]
                            counts[n] = counts.get(n, 0) + 1
            for n in totals:
                odds_map[n] = round(totals[n] / counts[n])
        return odds_map
    except:
        return {}

@st.cache_data(ttl=86400)
def sherdog_fighter_live(nome, url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        lutas = []
        tabela = soup.find("table", class_="new_table fighter")
        if tabela:
            for linha in tabela.find_all("tr")[1:]:
                cols = linha.find_all("td")
                if len(cols) >= 5:
                    lutas.append(cols[0].text.strip().lower())
        wins = sum(1 for l in lutas if l == "win")
        losses = sum(1 for l in lutas if l == "loss")
        altura = alcance = 0
        for bio in soup.find_all("div", class_="bio-holder"):
            t = bio.text
            if "HEIGHT" in t and "cm" in t:
                try: altura = float(t.split("cm")[0].split("/")[-1].strip())
                except: pass
            if "REACH" in t and "cm" in t:
                try: alcance = float(t.split("cm")[0].split("/")[-1].strip())
                except: pass
        return {"wins": wins, "losses": losses, "altura": altura, "alcance": alcance}
    except:
        return None

def _odds_para(nome, odds_map):
    return odds_map.get(nome.lower(), 0)

def prever_confronto(perfil_r, perfil_b, link_r="", link_b=""):
    try:
        odds_map = buscar_odds_map()
        nome_r = perfil_r["nome"]
        nome_b = perfil_b["nome"]

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

        def val(row, p, col, default=0.0):
            if row is None:
                return default
            try:
                v = float(row[f"{p}{col}"])
                return v if not np.isnan(v) else default
            except:
                return default

        # Tier 2: live Sherdog fallback for missing fighters
        live_r = sherdog_fighter_live(nome_r, link_r) if sr is None and link_r else None
        live_b = sherdog_fighter_live(nome_b, link_b) if sb is None and link_b else None

        def fighter_feats(row, p, live, perfil):
            if row is not None:
                return {
                    "ws": val(row,p,"current_win_streak"), "ls": val(row,p,"current_lose_streak"),
                    "lws": val(row,p,"longest_win_streak"), "w": val(row,p,"wins"), "l": val(row,p,"losses"),
                    "ss": val(row,p,"avg_SIG_STR_pct"), "td": val(row,p,"avg_TD_pct"), "sa": val(row,p,"avg_SUB_ATT"),
                    "h": val(row,p,"Height_cms"), "rch": val(row,p,"Reach_cms"), "age": val(row,p,"age"),
                    "rank": val(row,p,"match_weightclass_rank"),
                }
            elif live:
                return {"ws":1,"ls":0,"lws":3,"w":live["wins"],"l":live["losses"],
                    "ss":0,"td":0,"sa":0,"h":live["altura"],"rch":live["alcance"],"age":30,"rank":0}
            else:
                return {"ws":perfil["win_streak"],"ls":perfil["lose_streak"],"lws":perfil["longest_win_streak"],
                    "w":perfil["wins"],"l":perfil["losses"],"ss":perfil["sig_str_pct"]/100,
                    "td":perfil["td_pct"]/100,"sa":perfil["sub_att"],"h":0,"rch":0,"age":30,"rank":0}

        fr = fighter_feats(sr, pr, live_r, perfil_r)
        fb = fighter_feats(sb, pb, live_b, perfil_b)

        r_odds = _odds_para(nome_r, odds_map)
        b_odds = _odds_para(nome_b, odds_map)
        if r_odds == 0 and sr is not None:
            r_odds = val(sr, pr, "odds")
        if b_odds == 0 and sb is not None:
            b_odds = val(sb, pb, "odds")

        entrada = pd.DataFrame([[
            fr["ws"], fb["ws"], fr["ls"], fb["ls"], fr["lws"], fb["lws"],
            fr["w"], fb["w"], fr["l"], fb["l"],
            fr["ss"], fb["ss"], fr["td"], fb["td"], fr["sa"], fb["sa"],
            fr["h"], fb["h"], fr["rch"], fb["rch"], fr["age"], fb["age"],
            fr["rch"] - fb["rch"], fr["age"] - fb["age"], fr["ws"] - fb["ws"], fr["ss"] - fb["ss"],
            fr["rank"], fb["rank"], r_odds, b_odds,
        ]], columns=features)

        if isinstance(modelo, tuple):
            rf, lr = modelo
            prob = rf.predict_proba(entrada)[0] * 0.7 + lr.predict_proba(entrada)[0] * 0.3
        else:
            prob = modelo.predict_proba(entrada)[0]
        return round(prob[1] * 100, 1), round(prob[0] * 100, 1)
    except:
        return 50.0, 50.0

def conf_label(prob):
    if prob >= 70:
        return "High", "conf-high"
    elif prob >= 58:
        return "Medium", "conf-med"
    else:
        return "Toss-up", "conf-low"

def render_fight(luta, evento_nome, idx=0):
    perfil_r = buscar_lutador(luta["R_fighter"])
    perfil_b = buscar_lutador(luta["B_fighter"])
    pr_tmp = perfil_r or {"nome": luta["R_fighter"], "win_streak":1,"lose_streak":0,"longest_win_streak":3,"wins":0,"losses":0,"sig_str_pct":0,"td_pct":0,"sub_att":0}
    pb_tmp = perfil_b or {"nome": luta["B_fighter"], "win_streak":1,"lose_streak":0,"longest_win_streak":3,"wins":0,"losses":0,"sig_str_pct":0,"td_pct":0,"sub_att":0}
    prob_r, prob_b = prever_confronto(pr_tmp, pb_tmp, luta.get("R_link",""), luta.get("B_link",""))
    vencedor = luta["R_fighter"] if prob_r >= prob_b else luta["B_fighter"]
    conf, _ = conf_label(max(prob_r, prob_b))
    titulo = luta.get("title_bout", False)
    r_wins = perfil_r["wins"] if perfil_r else 0
    r_losses = perfil_r["losses"] if perfil_r else 0
    b_wins = perfil_b["wins"] if perfil_b else 0
    b_losses = perfil_b["losses"] if perfil_b else 0

    if titulo:
        st.markdown("🏆 **Title fight**")

    col1, col2, col3 = st.columns([3, 2, 3])
    with col1:
        st.markdown(f"**{luta['R_fighter']}**")
        st.caption(f"{r_wins}W · {r_losses}L")
    with col2:
        st.markdown(f"<div style='text-align:center;color:#555;font-size:12px'>vs<br><b style='color:#fff'>{vencedor.split()[0]}</b><br><small>{conf}</small></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"**{luta['B_fighter']}**")
        st.caption(f"{b_wins}W · {b_losses}L")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.progress(prob_r / 100, text=f"{luta['R_fighter'].split()[0]}: {prob_r}%")
    with col_p2:
        st.progress(prob_b / 100, text=f"{luta['B_fighter'].split()[0]}: {prob_b}%")

    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"👤 {luta['R_fighter'].split()[0]}", key=f"pr_{evento_nome}_{idx}_{luta['R_fighter']}"):
            st.session_state.lutador_selecionado = luta["R_fighter"]
            st.session_state.pagina = "perfil"
            st.rerun()
    with col2:
        if st.button(f"👤 {luta['B_fighter'].split()[0]}", key=f"pb_{evento_nome}_{idx}_{luta['B_fighter']}"):
            st.session_state.lutador_selecionado = luta["B_fighter"]
            st.session_state.pagina = "perfil"
            st.rerun()
    if st.button(f"⚔ View full matchup: {luta['R_fighter'].split()[0]} vs {luta['B_fighter'].split()[0]}", key=f"vs_{evento_nome}_{idx}", type="primary", use_container_width=True):
        st.session_state.nome_r = luta["R_fighter"]
        st.session_state.nome_b = luta["B_fighter"]
        st.session_state.pagina = "confronto"
        st.rerun()
    st.divider()

@st.cache_data(ttl=86400)
def encontrar_link_sherdog(nome):
    """Find a fighter's Sherdog URL from current event cards"""
    try:
        eventos = buscar_proximos_eventos()
        for ev in eventos:
            for luta in ev.get("lutas", []):
                if luta.get("R_fighter","").lower() == nome.lower() and luta.get("R_link"):
                    return luta["R_link"]
                if luta.get("B_fighter","").lower() == nome.lower() and luta.get("B_link"):
                    return luta["B_link"]
    except:
        pass
    return None

@st.cache_data(ttl=86400)
def perfil_insights(nome, sherdog_url):
    """Scrape rich profile + generate insights, cached per fighter"""
    if not sherdog_url:
        return None
    try:
        prof = scrape_full_profile(sherdog_url)
        ins = gerar_insights(prof)
        return {"profile": prof, "insights": ins}
    except:
        return None

def mostrar_perfil(nome):
    perfil = buscar_lutador(nome)
    if not perfil:
        st.error("Fighter not found.")
        return
    lutas = ultimas_lutas(nome)
    tags = gerar_tags(perfil)
    resumo = resumo_performance(lutas)

    if st.button("Back", key="back_perfil"):
        st.session_state.pagina = "home"
        st.rerun()

    iniciais = "".join([p[0] for p in nome.split()[:2]]).upper()
    col_av, col_info = st.columns([1, 5])
    with col_av:
        st.markdown(f"""<div style="width:72px;height:72px;border-radius:50%;background:#E24B4A22;border:2px solid #E24B4A;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:#E24B4A">{iniciais}</div>""", unsafe_allow_html=True)
    with col_info:
        st.markdown(f"## {perfil['nome']}")
        st.markdown(f"<span style='color:#555;font-size:13px'>{perfil['altura']} · {perfil['alcance']} reach · {perfil['peso']} · {perfil['stance']} · {perfil['idade']} yrs</span>", unsafe_allow_html=True)
        cols = st.columns(4)
        cols[0].metric("Wins", perfil["wins"])
        cols[1].metric("Losses", perfil["losses"])
        cols[2].metric("Win streak", perfil["win_streak"])
        cols[3].metric("Title bouts", perfil["title_bouts"])

    # Rich Sherdog insights
    sherdog_link = encontrar_link_sherdog(nome)
    rich = perfil_insights(nome, sherdog_link) if sherdog_link else None
    rich_tags = rich["insights"]["tags"] if rich else []

    all_tags = list(dict.fromkeys(tags + rich_tags))
    if all_tags:
        tags_html = " ".join([f'<span class="tag">{t}</span>' for t in all_tags])
        st.markdown(tags_html, unsafe_allow_html=True)

    if rich and rich["insights"]["insights"]:
        st.divider()
        st.markdown('<div class="section-title">Fighter insights</div>', unsafe_allow_html=True)
        for s in rich["insights"]["insights"]:
            st.markdown(f"<div style='padding:8px 12px;background:#16161a;border-left:3px solid #E24B4A;border-radius:4px;margin-bottom:6px;font-size:14px;color:#ddd'>{s}</div>", unsafe_allow_html=True)

    # Full fight history from Sherdog
    if rich and rich["profile"].get("fights"):
        st.divider()
        st.markdown('<div class="section-title">Fight history</div>', unsafe_allow_html=True)
        flog = rich["profile"]["fights"]
        show_all = st.toggle("Show full career", value=False, key="fhist_toggle")
        display_fights = flog if show_all else flog[:10]
        for f in display_fights:
            res = f["result"].upper()
            badge_color = "#3fb950" if res == "WIN" else ("#E24B4A" if res == "LOSS" else "#888")
            badge = "W" if res == "WIN" else ("L" if res == "LOSS" else "•")
            method = f.get("method", "")
            rnd = f.get("round", "")
            date = f.get("date", "")
            opp = f.get("opponent", "Unknown")
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:10px;padding:7px 10px;background:#141417;border-radius:5px;margin-bottom:4px'>"
                f"<span style='display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:{badge_color}22;color:{badge_color};font-weight:700;font-size:12px'>{badge}</span>"
                f"<span style='flex:1;color:#eee;font-size:14px'>vs <b>{opp}</b></span>"
                f"<span style='color:#888;font-size:12px;text-align:right'>{method}{(' · R'+rnd) if rnd else ''}<br>{date}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        if not show_all and len(flog) > 10:
            st.caption(f"Showing 10 of {len(flog)} fights — toggle above for full career")

    st.divider()
    st.markdown('<div class="section-title">Recent form</div>', unsafe_allow_html=True)

    form_dots = ""
    for l in lutas:
        cls = "form-dot-w" if l["resultado"] == "W" else "form-dot-l"
        form_dots += f'<span class="{cls}">{l["resultado"]}</span>'

    nv = sum(1 for l in lutas if l["resultado"] == "W")
    if nv == len(lutas):
        st.success(resumo)
    elif nv == 0:
        st.error(resumo)
    else:
        st.warning(resumo)

    st.markdown(form_dots, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    for i, luta in enumerate(lutas):
        col = [col1, col2, col3][i] if i < 3 else col3
        cor = "🟢" if luta["resultado"] == "W" else "🔴"
        with col:
            st.markdown(f"**{cor} vs {luta['adversario']}**")
            st.caption(f"{luta['metodo']} · R{luta['round']} · {luta['data'][:7]}")

    st.divider()
    st.markdown('<div class="section-title">Stats</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("KO/TKO", perfil["ko_wins"])
    col2.metric("Submissions", perfil["sub_wins"])
    col3.metric("Decisions", perfil["dec_wins"])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div style='color:#888;font-size:12px;margin-bottom:4px'>Striking accuracy</div>", unsafe_allow_html=True)
        st.progress(min(perfil["sig_str_pct"] / 100, 1.0), text=f"{perfil['sig_str_pct']}%")
    with col2:
        st.markdown(f"<div style='color:#888;font-size:12px;margin-bottom:4px'>Takedown accuracy</div>", unsafe_allow_html=True)
        st.progress(min(perfil["td_pct"] / 100, 1.0), text=f"{perfil['td_pct']}%")

    st.divider()
    st.markdown('<div class="section-title">Run a matchup</div>', unsafe_allow_html=True)
    adversario = st.selectbox("Select opponent", options=["Choose..."] + [l for l in lutadores if l.lower() != nome.lower()], key="adv_sel")
    if st.button("Predict fight", type="primary", key="predict_btn"):
        if adversario != "Choose...":
            st.session_state.nome_r = nome
            st.session_state.nome_b = adversario
            st.session_state.pagina = "confronto"
            st.rerun()

def mostrar_confronto(nome_r, nome_b):
    perfil_r = buscar_lutador(nome_r)
    perfil_b = buscar_lutador(nome_b)
    if not perfil_r or not perfil_b:
        st.error("Fighter not found.")
        return

    lutas_r = ultimas_lutas(nome_r)
    lutas_b = ultimas_lutas(nome_b)
    resumo_r = resumo_performance(lutas_r)
    resumo_b = resumo_performance(lutas_b)
    tags_r = gerar_tags(perfil_r)
    tags_b = gerar_tags(perfil_b)
    prob_r, prob_b = prever_confronto(perfil_r, perfil_b)
    vencedor = perfil_r["nome"] if prob_r > prob_b else perfil_b["nome"]
    conf, conf_cls = conf_label(max(prob_r, prob_b))

    if st.button("Back", key="back_conf"):
        st.session_state.pagina = "home"
        st.rerun()

    st.markdown(f"## {perfil_r['nome']} vs {perfil_b['nome']}")
    st.divider()

    col_r, col_b = st.columns(2)
    with col_r:
        st.markdown(f'<div class="fighter-name-r" style="font-size:18px">{perfil_r["nome"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<span style="color:#555;font-size:12px">{perfil_r["wins"]}W · {perfil_r["losses"]}L · {perfil_r["stance"]} · {perfil_r["altura"]}</span>', unsafe_allow_html=True)
        if tags_r:
            st.markdown(" ".join([f'<span class="tag">{t}</span>' for t in tags_r]), unsafe_allow_html=True)

        nv_r = sum(1 for l in lutas_r if l["resultado"] == "W")
        if nv_r == len(lutas_r):
            st.success(resumo_r)
        elif nv_r == 0:
            st.error(resumo_r)
        else:
            st.warning(resumo_r)

        form_r = "".join([f'<span class="form-dot-w">W</span>' if l["resultado"]=="W" else f'<span class="form-dot-l">L</span>' for l in lutas_r])
        st.markdown(form_r, unsafe_allow_html=True)

        st.markdown("**Last fights**")
        for l in lutas_r:
            cor = "🟢" if l["resultado"] == "W" else "🔴"
            st.markdown(f"{cor} vs {l['adversario']} — {l['metodo']} R{l['round']}")

        st.markdown("**Stats**")
        st.progress(min(perfil_r["sig_str_pct"]/100, 1.0), text=f"Striking: {perfil_r['sig_str_pct']}%")
        st.progress(min(perfil_r["td_pct"]/100, 1.0), text=f"Takedown: {perfil_r['td_pct']}%")
        cols = st.columns(3)
        cols[0].metric("KO", perfil_r["ko_wins"])
        cols[1].metric("Sub", perfil_r["sub_wins"])
        cols[2].metric("Dec", perfil_r["dec_wins"])

        if st.button(f"Full profile", key="full_r"):
            st.session_state.lutador_selecionado = nome_r
            st.session_state.pagina = "perfil"
            st.rerun()

    with col_b:
        st.markdown(f'<div class="fighter-name-b" style="font-size:18px">{perfil_b["nome"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<span style="color:#555;font-size:12px">{perfil_b["wins"]}W · {perfil_b["losses"]}L · {perfil_b["stance"]} · {perfil_b["altura"]}</span>', unsafe_allow_html=True)
        if tags_b:
            st.markdown(" ".join([f'<span class="tag">{t}</span>' for t in tags_b]), unsafe_allow_html=True)

        nv_b = sum(1 for l in lutas_b if l["resultado"] == "W")
        if nv_b == len(lutas_b):
            st.success(resumo_b)
        elif nv_b == 0:
            st.error(resumo_b)
        else:
            st.warning(resumo_b)

        form_b = "".join([f'<span class="form-dot-w">W</span>' if l["resultado"]=="W" else f'<span class="form-dot-l">L</span>' for l in lutas_b])
        st.markdown(form_b, unsafe_allow_html=True)

        st.markdown("**Last fights**")
        for l in lutas_b:
            cor = "🟢" if l["resultado"] == "W" else "🔴"
            st.markdown(f"{cor} vs {l['adversario']} — {l['metodo']} R{l['round']}")

        st.markdown("**Stats**")
        st.progress(min(perfil_b["sig_str_pct"]/100, 1.0), text=f"Striking: {perfil_b['sig_str_pct']}%")
        st.progress(min(perfil_b["td_pct"]/100, 1.0), text=f"Takedown: {perfil_b['td_pct']}%")
        cols = st.columns(3)
        cols[0].metric("KO", perfil_b["ko_wins"])
        cols[1].metric("Sub", perfil_b["sub_wins"])
        cols[2].metric("Dec", perfil_b["dec_wins"])

        if st.button(f"Full profile", key="full_b"):
            st.session_state.lutador_selecionado = nome_b
            st.session_state.pagina = "perfil"
            st.rerun()

    st.divider()
    st.markdown("### Prediction")

    st.markdown(f"""
    <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;text-align:center">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
            <span style="font-size:16px;font-weight:700;color:#E24B4A;width:80px;text-align:right">{prob_r}%</span>
            <div style="flex:1;height:8px;background:#1a1a1a;border-radius:4px;overflow:hidden;display:flex">
                <div style="width:{prob_r}%;background:#E24B4A;height:100%"></div>
                <div style="width:{prob_b}%;background:#378ADD;height:100%"></div>
            </div>
            <span style="font-size:16px;font-weight:700;color:#378ADD;width:80px">{prob_b}%</span>
        </div>
        <div style="font-size:13px;color:#555;margin-bottom:8px">Predicted winner</div>
        <div style="font-size:22px;font-weight:700;color:#fff">{vencedor}</div>
        <span class="{conf_cls}" style="margin-top:8px;display:inline-block">{conf} confidence</span>
    </div>
    """, unsafe_allow_html=True)

    # Model vs market
    odds_map = buscar_odds_map()
    r_odds = odds_map.get(nome_r.lower())
    b_odds = odds_map.get(nome_b.lower())
    if odds_map.get("_error"):
        st.caption("⚠ Live odds unavailable — " + odds_map["_error"])
    elif not odds_map:
        st.caption("⚠ Live odds map empty")
    elif r_odds is None or b_odds is None:
        st.caption(f"⚠ No live odds for this matchup (map has {len(odds_map)} fighters; looked for '{nome_r.lower()}' / '{nome_b.lower()}')")
    if r_odds is not None and b_odds is not None:
        market_fav = nome_r if r_odds < b_odds else nome_b
        def implied(o):
            return round((abs(o)/(abs(o)+100))*100 if o < 0 else (100/(o+100))*100, 1)
        imp_r = implied(r_odds); imp_b = implied(b_odds)
        agree = (market_fav == vencedor)
        verdict = "✓ Model agrees with the betting market" if agree else "⚡ Model DISAGREES — sees an upset"
        vcolor = "#3fb950" if agree else "#f0a020"
        st.markdown(f"""
        <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:16px;margin-top:10px">
            <div style="font-size:13px;color:#555;margin-bottom:12px">Model vs. betting market</div>
            <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px">
                <div style="flex:1;min-width:140px;background:#16161a;border-radius:8px;padding:10px">
                    <div style="color:#E24B4A;font-weight:600;font-size:13px">{nome_r}</div>
                    <div style="color:#fff;font-size:18px;font-weight:700">{'+' if r_odds>0 else ''}{r_odds}</div>
                    <div style="color:#777;font-size:11px">{imp_r}% implied</div>
                </div>
                <div style="flex:1;min-width:140px;background:#16161a;border-radius:8px;padding:10px">
                    <div style="color:#378ADD;font-weight:600;font-size:13px">{nome_b}</div>
                    <div style="color:#fff;font-size:18px;font-weight:700">{'+' if b_odds>0 else ''}{b_odds}</div>
                    <div style="color:#777;font-size:11px">{imp_b}% implied</div>
                </div>
            </div>
            <div style="color:{vcolor};font-weight:700;font-size:15px">{verdict}</div>
        </div>
        """, unsafe_allow_html=True)

    # Head-to-head comparison
    st.markdown('<div class="section-title" style="margin-top:18px">Head-to-head</div>', unsafe_allow_html=True)
    # Fighter name headers
    st.markdown(
        f"<div style='display:flex;align-items:center;padding:8px 0 12px 0'>"
        f"<span style='flex:1;text-align:right;color:#E24B4A;font-weight:700;font-size:16px'>{perfil_r['nome']}</span>"
        f"<span style='width:120px'></span>"
        f"<span style='flex:1;color:#378ADD;font-weight:700;font-size:16px'>{perfil_b['nome']}</span>"
        f"</div>", unsafe_allow_html=True
    )
    def adv_row(label, val_r, val_b, higher_better=True):
        try:
            fr = float(str(val_r).replace("cm","").replace("%","").strip())
            fb = float(str(val_b).replace("cm","").replace("%","").strip())
            if fr == fb:
                cr = cb = "#aaa"
            elif (fr > fb) == higher_better:
                cr, cb = "#3fb950", "#aaa"
            else:
                cr, cb = "#aaa", "#3fb950"
        except:
            cr = cb = "#ddd"
        st.markdown(
            f"<div style='display:flex;align-items:center;padding:11px 0;border-bottom:1px solid #1a1a1a'>"
            f"<span style='flex:1;text-align:right;color:{cr};font-weight:700;font-size:22px'>{val_r}</span>"
            f"<span style='width:120px;text-align:center;color:#666;font-size:13px;text-transform:uppercase;letter-spacing:0.5px'>{label}</span>"
            f"<span style='flex:1;color:{cb};font-weight:700;font-size:22px'>{val_b}</span>"
            f"</div>", unsafe_allow_html=True
        )
    adv_row("Record", f"{perfil_r['wins']}-{perfil_r['losses']}", f"{perfil_b['wins']}-{perfil_b['losses']}")
    adv_row("KO wins", perfil_r['ko_wins'], perfil_b['ko_wins'])
    adv_row("Sub wins", perfil_r['sub_wins'], perfil_b['sub_wins'])
    adv_row("Striking %", perfil_r['sig_str_pct'], perfil_b['sig_str_pct'])
    adv_row("Takedown %", perfil_r['td_pct'], perfil_b['td_pct'])
    adv_row("Win streak", perfil_r['win_streak'], perfil_b['win_streak'])

# Session state
if "pagina" not in st.session_state:
    st.session_state.pagina = "home"
if "lutador_selecionado" not in st.session_state:
    st.session_state.lutador_selecionado = None

# Header
st.markdown("""
<div style="background:#111;border-bottom:1px solid #1e1e1e;padding:14px 0;margin-bottom:0">
    <span style="font-size:20px;font-weight:700;color:#fff">UFC<span style="color:#E24B4A">analytics</span></span>
    <span style="color:#555;font-size:13px;margin-left:16px">Fight predictions · 65.8% accuracy</span>
</div>
""", unsafe_allow_html=True)

# Pages
if st.session_state.pagina == "perfil" and st.session_state.lutador_selecionado:
    mostrar_perfil(st.session_state.lutador_selecionado)

elif st.session_state.pagina == "confronto":
    mostrar_confronto(
        st.session_state.get("nome_r", ""),
        st.session_state.get("nome_b", "")
    )

else:
    tab1, tab2, tab3, tab4 = st.tabs(["Events", "Fighters", "Matchup", "Accuracy"])

    with tab1:
        col1, col2, col3 = st.columns(3)
        with st.spinner("Loading events..."):
            eventos_count = buscar_proximos_eventos()
        col1.metric("Model accuracy", "65.8%")
        col2.metric("Fights in dataset", f"{len(df):,}")
        col3.metric("Upcoming events", len(eventos_count))

        st.divider()

        if st.button("Refresh", key="refresh_events"):
            st.cache_data.clear()
            st.rerun()

        eventos = eventos_count

        if not eventos:
            st.error("Could not load events.")
        else:
            for evento in eventos:
                data_fmt = evento["data"]
                try:
                    data_fmt = datetime.strptime(evento["data"], "%Y-%m-%d").strftime("%b %d, %Y")
                except:
                    pass
                with st.expander(f"**{evento['nome']}** — {data_fmt}", expanded=(eventos.index(evento) == 0)):
                    for idx, luta in enumerate(evento["lutas"]):
                        render_fight(luta, evento["nome"], idx)

    with tab2:
        st.markdown("### Fighter search")
        busca = st.text_input("Type a fighter name...", placeholder="e.g. Jon Jones, Islam Makhachev")
        if busca and len(busca) >= 2:
            resultados = [l for l in lutadores if busca.lower() in l.lower()][:20]
            if resultados:
                st.markdown(f"*{len(resultados)} fighters found*")
                cols = st.columns(2)
                for i, nome in enumerate(resultados):
                    perfil = buscar_lutador(nome)
                    with cols[i % 2]:
                        if perfil:
                            tags = gerar_tags(perfil)
                            tags_html = " ".join([f'<span class="tag">{t}</span>' for t in tags[:2]])
                            st.markdown(f"""
                            <div class="fight-card" style="margin-bottom:8px">
                                <div style="font-size:14px;font-weight:600;color:#fff">{perfil["nome"]}</div>
                                <div style="color:#555;font-size:12px">{perfil["wins"]}W · {perfil["losses"]}L · {perfil["stance"]}</div>
                                <div style="margin-top:6px">{tags_html}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button("View profile", key=f"search_{nome}"):
                                st.session_state.lutador_selecionado = nome
                                st.session_state.pagina = "perfil"
                                st.rerun()
            else:
                st.warning("No fighters found.")
        else:
            st.markdown('<div style="color:#555;font-size:13px">Start typing to search 2,249 fighters</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown("### Fight matchup")
        col1, col2 = st.columns(2)
        with col1:
            nome_r = st.selectbox("Red corner", options=["Choose..."] + lutadores, index=0, key="sel_r")
        with col2:
            nome_b = st.selectbox("Blue corner", options=["Choose..."] + lutadores, index=0, key="sel_b")

        if st.button("Predict fight", type="primary"):
            if nome_r == "Choose..." or nome_b == "Choose...":
                st.warning("Select both fighters.")
            elif nome_r == nome_b:
                st.warning("Select different fighters.")
            else:
                st.session_state.nome_r = nome_r
                st.session_state.nome_b = nome_b
                st.session_state.pagina = "confronto"
                st.rerun()

    with tab4:
        st.markdown("### Prediction accuracy")
        import json, os
        acc_file = "accuracy_history.json"
        if os.path.exists(acc_file):
            with open(acc_file) as f:
                history = json.load(f)

            total_correct = sum(e["correct"] for e in history)
            total_fights = sum(e["total"] for e in history)
            overall_acc = round(total_correct / total_fights * 100, 1) if total_fights > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Overall accuracy", f"{overall_acc}%")
            col2.metric("Total correct", total_correct)
            col3.metric("Events tracked", len(history))

            st.divider()

            for evento in reversed(history):
                acc = evento["accuracy"]
                color = "success" if acc >= 65 else "warning" if acc >= 50 else "error"
                with st.expander(f"**{evento['event']}** — {evento['correct']}/{evento['total']} ({acc}%)", expanded=True):
                    for fight in evento.get("fights", []):
                        icon = "✅" if fight["correct"] else "❌"
                        st.markdown(f"{icon} **{fight['R']} vs {fight['B']}**")
                        st.caption(f"Predicted: {fight['predicted']} | Actual: {fight['actual']}")
        else:
            st.info("No accuracy data yet. Results will appear after each event.")
