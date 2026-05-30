
import pandas as pd
import numpy as np
import requests
import joblib
import json
import os
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

print("Starting UFC auto-update...")

df = pd.read_csv("ufc_master_clean.csv")
modelo = joblib.load("modelo_ufc_v3.pkl")
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

def get_prediction(nome_r, nome_b):
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
        return nome_r if prob[1] > prob[0] else nome_b
    except:
        return None

# Fetch ESPN results
url = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
data = resp.json()

accuracy_history = []
predictions_history = []

if os.path.exists("accuracy_history.json"):
    with open("accuracy_history.json") as f:
        accuracy_history = json.load(f)

if os.path.exists("predictions_history.json"):
    with open("predictions_history.json") as f:
        predictions_history = json.load(f)

for evento in data.get("events", []):
    event_name = evento.get("name")
    event_date = evento.get("date", "")[:10]
    already_processed = any(e["event"] == event_name for e in accuracy_history)

    completed = []
    upcoming = []

    for luta in evento.get("competitions", []):
        competidores = luta.get("competitors", [])
        if len(competidores) < 2:
            continue
        r = competidores[0].get("athlete", {}).get("displayName", "N/A")
        b = competidores[1].get("athlete", {}).get("displayName", "N/A")
        status = luta.get("status", {}).get("type", {}).get("name", "")
        winner = ""
        for c in competidores:
            if c.get("winner"):
                winner = c.get("athlete", {}).get("displayName", "")
        if status == "STATUS_FINAL" and winner:
            completed.append({"R": r, "B": b, "winner": winner})
        else:
            upcoming.append({"R": r, "B": b})

    # Check accuracy on completed fights
    if completed and not already_processed:
        print(f"Checking results: {event_name}")
        correct = 0
        total = 0
        fight_results = []
        for fight in completed:
            predicted = get_prediction(fight["R"], fight["B"])
            if predicted:
                is_correct = predicted.lower() == fight["winner"].lower()
                if is_correct:
                    correct += 1
                total += 1
                fight_results.append({
                    "R": fight["R"], "B": fight["B"],
                    "predicted": predicted,
                    "actual": fight["winner"],
                    "correct": is_correct
                })
                print(f"  {'✓' if is_correct else '✗'} {fight['R']} vs {fight['B']} — {predicted} vs {fight['winner']}")
        if total > 0:
            acc = round(correct / total * 100, 1)
            accuracy_history.append({
                "event": event_name, "date": event_date,
                "correct": correct, "total": total, "accuracy": acc
            })
            predictions_history.append({
                "event": event_name, "date": event_date,
                "fights": fight_results
            })
            print(f"Accuracy: {correct}/{total} = {acc}%")

    # Save upcoming predictions
    if upcoming:
        preds = []
        for fight in upcoming:
            predicted = get_prediction(fight["R"], fight["B"])
            if predicted:
                preds.append({"R": fight["R"], "B": fight["B"], "predicted": predicted})
        with open("upcoming_predictions.json", "w") as f:
            json.dump({"event": event_name, "date": event_date, "predictions": preds}, f, indent=2)

# Save history
with open("accuracy_history.json", "w") as f:
    json.dump(accuracy_history, f, indent=2)
with open("predictions_history.json", "w") as f:
    json.dump(predictions_history, f, indent=2)

# Quick retrain
df_model = df[df["Winner"].isin(["Red", "Blue"])].copy()
df_model["resultado"] = (df_model["Winner"] == "Red").astype(int)
df_model = df_model[features_v2 + ["resultado"]].dropna()
X = df_model[features_v2]
y = df_model["resultado"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
modelo_new = RandomForestClassifier(n_estimators=200, random_state=42)
modelo_new.fit(X_train, y_train)
acc = accuracy_score(y_test, modelo_new.predict(X_test))
print(f"Model accuracy: {acc:.1%}")
joblib.dump(modelo_new, "modelo_ufc_v3.pkl")
print("Done!")
