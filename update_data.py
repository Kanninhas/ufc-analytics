
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import joblib
import json
import time
import os
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

print("Starting UFC auto-update...")

df = pd.read_csv("ufc_master_clean.csv")
print(f"Dataset: {len(df)} fights")

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

def safe_float(val, default=0.0):
    try:
        v = float(val)
        return v if not np.isnan(v) else default
    except:
        return default

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
        return {"wins": wins, "losses": losses, "ko_wins": ko_wins, "sub_wins": sub_wins}
    except:
        return None

def fetch_espn_events():
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = resp.json()
        events = []
        for evento in data.get("events", []):
            event_name = evento.get("name")
            event_date = evento.get("date", "")[:10]
            fights = []
            for luta in evento.get("competitions", []):
                competidores = luta.get("competitors", [])
                if len(competidores) >= 2:
                    r = competidores[0].get("athlete", {}).get("displayName", "N/A")
                    b = competidores[1].get("athlete", {}).get("displayName", "N/A")
                    status = luta.get("status", {}).get("type", {}).get("name", "")
                    winner = ""
                    for c in competidores:
                        if c.get("winner"):
                            winner = c.get("athlete", {}).get("displayName", "")
                    fights.append({
                        "R": r, "B": b,
                        "status": status,
                        "winner": winner
                    })
            events.append({
                "name": event_name,
                "date": event_date,
                "fights": fights
            })
        return events
    except:
        return []

def get_prediction(nome_r, nome_b, modelo, df):
    try:
        lutas_r = df[df["R_fighter"].str.lower() == nome_r.lower()]
        lutas_r2 = df[df["B_fighter"].str.lower() == nome_r.lower()]
        lutas_b = df[df["B_fighter"].str.lower() == nome_b.lower()]
        lutas_b2 = df[df["R_fighter"].str.lower() == nome_b.lower()]
        if len(lutas_r) > 0:
            sr = lutas_r.sort_values("date", ascending=False).iloc[0]
            pr = "R_"
        elif len(lutas_r2) > 0:
            sr = lutas_r2.sort_values("date", ascending=False).iloc[0]
            pr = "B_"
        else:
            return None
        if len(lutas_b) > 0:
            sb = lutas_b.sort_values("date", ascending=False).iloc[0]
            pb = "B_"
        elif len(lutas_b2) > 0:
            sb = lutas_b2.sort_values("date", ascending=False).iloc[0]
            pb = "R_"
        else:
            return None
        entrada = pd.DataFrame([[
            safe_float(sr[f"{pr}current_win_streak"]),
            safe_float(sb[f"{pb}current_win_streak"]),
            safe_float(sr[f"{pr}current_lose_streak"]),
            safe_float(sb[f"{pb}current_lose_streak"]),
            safe_float(sr[f"{pr}longest_win_streak"]),
            safe_float(sb[f"{pb}longest_win_streak"]),
            safe_float(sr[f"{pr}wins"]),
            safe_float(sb[f"{pb}wins"]),
            safe_float(sr[f"{pr}losses"]),
            safe_float(sb[f"{pb}losses"]),
            safe_float(sr[f"{pr}avg_SIG_STR_pct"]),
            safe_float(sb[f"{pb}avg_SIG_STR_pct"]),
            safe_float(sr[f"{pr}avg_TD_pct"]),
            safe_float(sb[f"{pb}avg_TD_pct"]),
            safe_float(sr[f"{pr}avg_SUB_ATT"]),
            safe_float(sb[f"{pb}avg_SUB_ATT"]),
            safe_float(sr[f"{pr}Height_cms"]),
            safe_float(sb[f"{pb}Height_cms"]),
            safe_float(sr[f"{pr}Reach_cms"]),
            safe_float(sb[f"{pb}Reach_cms"]),
            safe_float(sr[f"{pr}age"]),
            safe_float(sb[f"{pb}age"]),
            safe_float(sr.get("reach_dif", 0)),
            safe_float(sr.get("age_dif", 0)),
            safe_float(sr.get("win_streak_dif", 0)),
            safe_float(sr.get("sig_str_dif", 0)),
            safe_float(sr.get(f"{pr}match_weightclass_rank", 0)),
            safe_float(sb.get(f"{pb}match_weightclass_rank", 0)),
            safe_float(sr.get("R_odds", 0)),
            safe_float(sr.get("B_odds", 0)),
        ]], columns=features_v2)
        prob = modelo.predict_proba(entrada)[0]
        predicted_winner = nome_r if prob[1] > prob[0] else nome_b
        return predicted_winner
    except:
        return None

# Load model
modelo = joblib.load("modelo_ufc_v3.pkl")

# Load history files
predictions_history = []
accuracy_history = []

if os.path.exists("predictions_history.json"):
    with open("predictions_history.json") as f:
        predictions_history = json.load(f)

if os.path.exists("accuracy_history.json"):
    with open("accuracy_history.json") as f:
        accuracy_history = json.load(f)

# Fetch ESPN events
events = fetch_espn_events()
print(f"ESPN events found: {len(events)}")

for event in events:
    event_name = event["name"]
    event_date = event["date"]
    fights = event["fights"]

    # Check if event already processed
    already_processed = any(e["event"] == event_name for e in accuracy_history)

    completed_fights = [f for f in fights if f["status"] == "STATUS_FINAL" and f["winner"]]
    upcoming_fights = [f for f in fights if f["status"] != "STATUS_FINAL"]

    # Process completed fights for accuracy
    if completed_fights and not already_processed:
        print(f"
Processing results: {event_name}")
        correct = 0
        total = 0
        fight_results = []

        for fight in completed_fights:
            predicted = get_prediction(fight["R"], fight["B"], modelo, df)
            if predicted:
                is_correct = predicted.lower() == fight["winner"].lower()
                if is_correct:
                    correct += 1
                total += 1
                fight_results.append({
                    "R": fight["R"],
                    "B": fight["B"],
                    "predicted": predicted,
                    "actual": fight["winner"],
                    "correct": is_correct
                })
                print(f"  {'✓' if is_correct else '✗'} {fight['R']} vs {fight['B']} — predicted: {predicted} | actual: {fight['winner']}")

        if total > 0:
            acc = round(correct / total * 100, 1)
            accuracy_history.append({
                "event": event_name,
                "date": event_date,
                "correct": correct,
                "total": total,
                "accuracy": acc
            })
            predictions_history.append({
                "event": event_name,
                "date": event_date,
                "fights": fight_results
            })
            print(f"Accuracy: {correct}/{total} ({acc}%)")

    # Generate predictions for upcoming fights
    if upcoming_fights:
        print(f"
Upcoming fights: {event_name}")
        upcoming_predictions = []
        for fight in upcoming_fights:
            predicted = get_prediction(fight["R"], fight["B"], modelo, df)
            if predicted:
                upcoming_predictions.append({
                    "R": fight["R"],
                    "B": fight["B"],
                    "predicted": predicted
                })

        # Save upcoming predictions
        with open("upcoming_predictions.json", "w") as f:
            json.dump({
                "event": event_name,
                "date": event_date,
                "predictions": upcoming_predictions
            }, f, indent=2)
        print(f"Saved {len(upcoming_predictions)} upcoming predictions")

    # Update fighter records from Sherdog for fighters with zero wins
    print(f"
Updating fighter records...")
    todos = pd.concat([df["R_fighter"], df["B_fighter"]]).unique()
    updated = 0
    for nome in todos:
        lutas_r = df[df["R_fighter"].str.lower() == nome.lower()]
        lutas_b = df[df["B_fighter"].str.lower() == nome.lower()]
        if len(lutas_r) > 0:
            wins = lutas_r.sort_values("date", ascending=False).iloc[0]["R_wins"]
        elif len(lutas_b) > 0:
            wins = lutas_b.sort_values("date", ascending=False).iloc[0]["B_wins"]
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
    print(f"Updated {updated} fighters")

# Save history files
with open("accuracy_history.json", "w") as f:
    json.dump(accuracy_history, f, indent=2)

with open("predictions_history.json", "w") as f:
    json.dump(predictions_history, f, indent=2)

# Retrain model
df_model = df[df["Winner"].isin(["Red", "Blue"])].copy()
df_model["resultado"] = (df_model["Winner"] == "Red").astype(int)
df_model = df_model[features_v2 + ["resultado"]].dropna()

X = df_model[features_v2]
y = df_model["resultado"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
modelo_new = RandomForestClassifier(n_estimators=200, random_state=42)
modelo_new.fit(X_train, y_train)
acc = accuracy_score(y_test, modelo_new.predict(X_test))
print(f"
Model retrained: {acc:.1%}")

# Save everything
df.to_csv("ufc_master_clean.csv", index=False)
joblib.dump(modelo_new, "modelo_ufc_v3.pkl")
joblib.dump(features_v2, "features_v3.pkl")
print("All files saved!")
