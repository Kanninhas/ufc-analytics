import pandas as pd
import numpy as np
import requests
import joblib
import json
import os

print("Starting UFC auto-update...")

df = pd.read_csv("ufc_master_clean.csv")
modelo = joblib.load("modelo_ufc_v3.pkl")
features_v2 = joblib.load("features_v3.pkl")
print(f"Dataset: {len(df)} fights")

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

url = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
data = resp.json()

accuracy_history = json.load(open("accuracy_history.json")) if os.path.exists("accuracy_history.json") else []
predictions_history = json.load(open("predictions_history.json")) if os.path.exists("predictions_history.json") else []

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
    if completed and not already_processed:
        print(f"Results: {event_name}")
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
                fight_results.append({"R": fight["R"], "B": fight["B"], "predicted": predicted, "actual": fight["winner"], "correct": is_correct})
        if total > 0:
            acc = round(correct / total * 100, 1)
            accuracy_history.append({"event": event_name, "date": event_date, "correct": correct, "total": total, "accuracy": acc})
            predictions_history.append({"event": event_name, "date": event_date, "fights": fight_results})
            print(f"Accuracy: {correct}/{total} = {acc}%")
    if upcoming:
        preds = [{"R": f["R"], "B": f["B"], "predicted": get_prediction(f["R"], f["B"])} for f in upcoming if get_prediction(f["R"], f["B"])]
        json.dump({"event": event_name, "date": event_date, "predictions": preds}, open("upcoming_predictions.json", "w"), indent=2)

json.dump(accuracy_history, open("accuracy_history.json", "w"), indent=2)
json.dump(predictions_history, open("predictions_history.json", "w"), indent=2)
print("Done!")
