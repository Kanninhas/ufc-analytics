
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import joblib
import time
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

print("Starting UFC data update...")

# Load existing dataset
df = pd.read_csv("ufc_master_clean.csv")
print(f"Current dataset: {len(df)} fights")

def buscar_sherdog(nome):
    try:
        search_url = f"https://www.sherdog.com/stats/fightfinder?SearchTxt={nome.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        resultado = soup.find("table", class_="fightfinder_result")
        if not resultado:
            return None
        primeira_linha = resultado.find_all("tr")[1]
        link = primeira_linha.find("a")
        if not link:
            return None
        fighter_url = "https://www.sherdog.com" + link["href"]
        time.sleep(1)
        resp2 = requests.get(fighter_url, headers=headers, timeout=10)
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        lutas = []
        tabela = soup2.find("table", class_="new_table fighter")
        if tabela:
            for linha in tabela.find_all("tr")[1:]:
                cols = linha.find_all("td")
                if len(cols) >= 5:
                    lutas.append({
                        "resultado": cols[0].text.strip().lower(),
                        "metodo": cols[3].text.strip()[:30],
                    })
        wins = sum(1 for l in lutas if l["resultado"] == "win")
        losses = sum(1 for l in lutas if l["resultado"] == "loss")
        ko_wins = sum(1 for l in lutas if l["resultado"] == "win" and ("ko" in l["metodo"].lower() or "tko" in l["metodo"].lower()))
        sub_wins = sum(1 for l in lutas if l["resultado"] == "win" and "sub" in l["metodo"].lower())
        dec_wins = sum(1 for l in lutas if l["resultado"] == "win" and "dec" in l["metodo"].lower())
        return {"wins": wins, "losses": losses, "ko_wins": ko_wins, "sub_wins": sub_wins, "dec_wins": dec_wins}
    except:
        return None

def fetch_espn_results():
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = resp.json()
        fights = []
        for event in data.get("events", []):
            event_name = event.get("name")
            event_date = event.get("date", "")[:10]
            for fight in event.get("competitions", []):
                competitors = fight.get("competitors", [])
                if len(competitors) >= 2:
                    r = competitors[0].get("athlete", {}).get("displayName", "N/A")
                    b = competitors[1].get("athlete", {}).get("displayName", "N/A")
                    status = fight.get("status", {}).get("type", {}).get("name", "")
                    winner = ""
                    if status == "STATUS_FINAL":
                        for c in competitors:
                            if c.get("winner"):
                                winner = c.get("athlete", {}).get("displayName", "")
                    fights.append({
                        "evento": event_name,
                        "data": event_date,
                        "R_fighter": r,
                        "B_fighter": b,
                        "status": status,
                        "winner": winner
                    })
        return fights
    except:
        return []

# Fetch latest ESPN data
fights = fetch_espn_results()
print(f"ESPN fights found: {len(fights)}")

# Update fighters with Sherdog data
todos = pd.concat([df["R_fighter"], df["B_fighter"]]).unique()
updated = 0
for nome in todos:
    lutas_r = df[df["R_fighter"].str.lower() == nome.lower()]
    lutas_b = df[df["B_fighter"].str.lower() == nome.lower()]
    if len(lutas_r) > 0:
        stats = lutas_r.sort_values("date", ascending=False).iloc[0]
        wins = stats["R_wins"]
    elif len(lutas_b) > 0:
        stats = lutas_b.sort_values("date", ascending=False).iloc[0]
        wins = stats["B_wins"]
    else:
        continue
    if wins == 0:
        dados = buscar_sherdog(nome)
        time.sleep(1.5)
        if dados and dados["wins"] > 0:
            mask_r = df["R_fighter"].str.lower() == nome.lower()
            mask_b = df["B_fighter"].str.lower() == nome.lower()
            df.loc[mask_r, "R_wins"] = dados["wins"]
            df.loc[mask_r, "R_losses"] = dados["losses"]
            df.loc[mask_b, "B_wins"] = dados["wins"]
            df.loc[mask_b, "B_losses"] = dados["losses"]
            updated += 1

print(f"Fighters updated: {updated}")

# Retrain model
features_v2 = [
    "R_current_win_streak", "B_current_win_streak",
    "R_current_lose_streak", "B_current_lose_streak",
    "R_longest_win_streak", "B_longest_win_streak",
    "R_wins", "B_wins", "R_losses", "B_losses",
    "R_avg_SIG_STR_pct", "B_avg_SIG_STR_pct",
    "R_avg_TD_pct", "B_avg_TD_pct",
    "R_avg_SUB_ATT", "B_avg_SUB_ATT",
    "R_Height_cms", "B_Height_cms",
    "R_Reach_cms", "B_Reach_cms",
    "R_age", "B_age",
    "reach_dif", "age_dif", "win_streak_dif", "sig_str_dif",
    "R_match_weightclass_rank", "B_match_weightclass_rank",
    "R_odds", "B_odds",
]

df_model = df[df["Winner"].isin(["Red", "Blue"])].copy()
df_model["resultado"] = (df_model["Winner"] == "Red").astype(int)
df_model = df_model[features_v2 + ["resultado"]].dropna()

X = df_model[features_v2]
y = df_model["resultado"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=200, random_state=42)
model.fit(X_train, y_train)
accuracy = accuracy_score(y_test, model.predict(X_test))
print(f"Model accuracy: {accuracy:.1%}")

# Save everything
df.to_csv("ufc_master_clean.csv", index=False)
joblib.dump(model, "modelo_ufc_v3.pkl")
joblib.dump(features_v2, "features_v3.pkl")
print("All files saved!")
