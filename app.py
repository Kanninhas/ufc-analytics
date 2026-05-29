
import streamlit as st
import pandas as pd
import joblib
import numpy as np
import requests
import warnings
from groq import Groq
warnings.filterwarnings("ignore")

st.set_page_config(page_title="UFC Analytics", page_icon="🥊", layout="wide")

import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

@st.cache_data
def carregar_dados():
    df = pd.read_csv("ufc_master_clean.csv")
    modelo = joblib.load("modelo_ufc_v2.pkl")
    features = joblib.load("features.pkl")
    todos = pd.concat([df["R_fighter"], df["B_fighter"]]).unique()
    lutadores = sorted(set([l.strip() for l in todos if isinstance(l, str)]))
    return df, modelo, features, lutadores

df, modelo, features, lutadores = carregar_dados()

@st.cache_data(ttl=3600)
def buscar_card_espn():
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = resp.json()
        lutas = []
        for evento in data.get("events", []):
            nome_evento = evento.get("name")
            data_evento = evento.get("date", "")[:10]
            for luta in evento.get("competitions", []):
                competidores = luta.get("competitors", [])
                if len(competidores) >= 2:
                    r = competidores[0].get("athlete", {}).get("displayName", "N/A")
                    b = competidores[1].get("athlete", {}).get("displayName", "N/A")
                    titulo = luta.get("notes", [{}])[0].get("headline", "") if luta.get("notes") else ""
                    lutas.append({
                        "evento": nome_evento,
                        "data": data_evento,
                        "R_fighter": r,
                        "B_fighter": b,
                        "title_bout": "title" in titulo.lower() if titulo else False
                    })
        return pd.DataFrame(lutas)
    except:
        return pd.DataFrame()

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
    lutas_r = df[df["R_fighter"].str.lower() == nome.lower()]
    lutas_b = df[df["B_fighter"].str.lower() == nome.lower()]
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
        "idade": f"{safe_float(stats[f'{p}age']):.0f} anos" if safe_float(stats[f"{p}age"]) > 0 else "N/A",
    }

def ultimas_lutas(nome, n=3):
    lutas_r = df[df["R_fighter"].str.lower() == nome.lower()].copy()
    lutas_r["lado"] = "R"
    lutas_b = df[df["B_fighter"].str.lower() == nome.lower()].copy()
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
            resultado = "Vitória" if lado == "R" else "Derrota"
        elif winner == "Blue":
            resultado = "Vitória" if lado == "B" else "Derrota"
        else:
            resultado = "Empate"
        lutas.append({
            "adversario": adversario,
            "data": luta["date"],
            "resultado": resultado,
            "metodo": str(luta["finish"]) if pd.notna(luta["finish"]) else "N/A",
            "round": luta["finish_round"],
            "tempo": luta["finish_round_time"],
        })
    return lutas

def gerar_analise(perfil, lutas):
    ultimas = ""
    for l in lutas:
        ultimas += f"- {l['resultado']} vs {l['adversario']} ({l['data']}) via {l['metodo']} R{l['round']}\n"
    prompt = f"""Você é um analista especialista em MMA e UFC.
Com base nos dados abaixo, escreva uma análise curta (3-4 frases) sobre o momento atual do lutador.
Destaque pontos fortes, pontos fracos e como ele chega para a próxima luta.
Seja direto e use linguagem de analista esportivo.

Lutador: {perfil['nome']}
Cartel: {perfil['wins']}V {perfil['losses']}D
Sequência atual: {perfil['win_streak']} vitórias / {perfil['lose_streak']} derrotas
KO/Sub/Decisão: {perfil['ko_wins']}/{perfil['sub_wins']}/{perfil['dec_wins']}
Precisão striking: {perfil['sig_str_pct']}%
Títulos disputados: {perfil['title_bouts']}

Últimas lutas:
{ultimas}

Escreva apenas a análise, sem títulos ou introdução."""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        resposta = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return resposta.choices[0].message.content
    except:
        return "Análise indisponível no momento."

def gerar_tags(perfil):
    tags = []
    total = perfil["ko_wins"] + perfil["sub_wins"] + perfil["dec_wins"]
    if total > 0:
        if perfil["ko_wins"] / total > 0.4:
            tags.append("Poder de nocaute")
        if perfil["sub_wins"] / total > 0.3:
            tags.append("Grappling de elite")
        if perfil["dec_wins"] / total > 0.5:
            tags.append("Volume e resistência")
    if perfil["sig_str_pct"] >= 60:
        tags.append("Striking preciso")
    if perfil["td_pct"] >= 50:
        tags.append("Takedown eficiente")
    if perfil["win_streak"] >= 3:
        tags.append("Forma ascendente")
    elif perfil["lose_streak"] >= 2:
        tags.append("Momento delicado")
    if perfil["title_bouts"] >= 3:
        tags.append("Experiência no título")
    return tags

def prever_luta_espn(nome_r, nome_b):
    perfil_r = buscar_lutador(nome_r)
    perfil_b = buscar_lutador(nome_b)
    if not perfil_r or not perfil_b:
        return 50.0, 50.0, perfil_r, perfil_b
    try:
        entrada = [[
            perfil_r["win_streak"], perfil_b["win_streak"],
            perfil_r["lose_streak"], perfil_b["lose_streak"],
            perfil_r["longest_win_streak"], perfil_b["longest_win_streak"],
            perfil_r["wins"], perfil_b["wins"],
            perfil_r["losses"], perfil_b["losses"],
            perfil_r["sig_str_pct"] / 100, perfil_b["sig_str_pct"] / 100,
            perfil_r["td_pct"] / 100, perfil_b["td_pct"] / 100,
            perfil_r["sub_att"], perfil_b["sub_att"],
            0, 0, 0, 0, 0, 0,
        ]]
        prob = modelo.predict_proba(entrada)[0]
        return round(prob[1] * 100, 1), round(prob[0] * 100, 1), perfil_r, perfil_b
    except:
        return 50.0, 50.0, perfil_r, perfil_b

st.markdown("## UFC Analytics")
st.markdown("Previsão de lutas com inteligência artificial")
st.divider()

aba1, aba2 = st.tabs(["Analisar confronto", "Próximo evento"])

with aba1:
    col1, col2 = st.columns(2)
    with col1:
        nome_r = st.selectbox("Canto Vermelho", options=["Selecione um lutador..."] + lutadores, index=0, key="sel_r")
    with col2:
        nome_b = st.selectbox("Canto Azul", options=["Selecione um lutador..."] + lutadores, index=0, key="sel_b")

    if st.button("Analisar confronto", type="primary"):
        if nome_r == "Selecione um lutador..." or nome_b == "Selecione um lutador...":
            st.warning("Selecione os dois lutadores para continuar.")
        elif nome_r == nome_b:
            st.warning("Selecione lutadores diferentes.")
        else:
            perfil_r = buscar_lutador(nome_r)
            perfil_b = buscar_lutador(nome_b)
            if not perfil_r:
                st.error(f"Dados de '{nome_r}' não encontrados.")
            elif not perfil_b:
                st.error(f"Dados de '{nome_b}' não encontrados.")
            else:
                lutas_r = ultimas_lutas(nome_r)
                lutas_b = ultimas_lutas(nome_b)
                tags_r = gerar_tags(perfil_r)
                tags_b = gerar_tags(perfil_b)
                entrada = [[
                    perfil_r["win_streak"], perfil_b["win_streak"],
                    perfil_r["lose_streak"], perfil_b["lose_streak"],
                    perfil_r["longest_win_streak"], perfil_b["longest_win_streak"],
                    perfil_r["wins"], perfil_b["wins"],
                    perfil_r["losses"], perfil_b["losses"],
                    perfil_r["sig_str_pct"] / 100, perfil_b["sig_str_pct"] / 100,
                    perfil_r["td_pct"] / 100, perfil_b["td_pct"] / 100,
                    perfil_r["sub_att"], perfil_b["sub_att"],
                    0, 0, 0, 0, 0, 0,
                ]]
                prob = modelo.predict_proba(entrada)[0]
                prob_r = round(prob[1] * 100, 1)
                prob_b = round(prob[0] * 100, 1)
                vencedor = perfil_r["nome"] if prob[1] > prob[0] else perfil_b["nome"]
                with st.spinner("Gerando análise de IA..."):
                    analise_r = gerar_analise(perfil_r, lutas_r)
                    analise_b = gerar_analise(perfil_b, lutas_b)
                col_r, col_b = st.columns(2)
                with col_r:
                    st.markdown(f"### {perfil_r['nome']}")
                    if tags_r:
                        st.markdown(" ".join([f"`{t}`" for t in tags_r]))
                    st.markdown(f"**{perfil_r['wins']}V · {perfil_r['losses']}D** | {perfil_r['stance']} | {perfil_r['idade']}")
                    st.markdown(f"Altura: {perfil_r['altura']} | Alcance: {perfil_r['alcance']} | Peso: {perfil_r['peso']}")
                    st.progress(min(perfil_r["sig_str_pct"] / 100, 1.0), text=f"Precisão striking: {perfil_r['sig_str_pct']}%")
                    st.progress(min(perfil_r["td_pct"] / 100, 1.0), text=f"Precisão takedown: {perfil_r['td_pct']}%")
                    st.markdown(f"KO: {perfil_r['ko_wins']} | Sub: {perfil_r['sub_wins']} | Dec: {perfil_r['dec_wins']}")
                    st.markdown(f"Sequência: {perfil_r['win_streak']} vitórias | Títulos: {perfil_r['title_bouts']}")
                    st.markdown("**Últimas lutas**")
                    for l in lutas_r:
                        cor = "🟢" if l["resultado"] == "Vitória" else ("🔴" if l["resultado"] == "Derrota" else "🟡")
                        st.markdown(f"{cor} vs {l['adversario']} ({l['data']}) — {l['metodo']} R{l['round']}")
                    st.divider()
                    st.markdown("**Análise IA**")
                    st.info(analise_r)
                with col_b:
                    st.markdown(f"### {perfil_b['nome']}")
                    if tags_b:
                        st.markdown(" ".join([f"`{t}`" for t in tags_b]))
                    st.markdown(f"**{perfil_b['wins']}V · {perfil_b['losses']}D** | {perfil_b['stance']} | {perfil_b['idade']}")
                    st.markdown(f"Altura: {perfil_b['altura']} | Alcance: {perfil_b['alcance']} | Peso: {perfil_b['peso']}")
                    st.progress(min(perfil_b["sig_str_pct"] / 100, 1.0), text=f"Precisão striking: {perfil_b['sig_str_pct']}%")
                    st.progress(min(perfil_b["td_pct"] / 100, 1.0), text=f"Precisão takedown: {perfil_b['td_pct']}%")
                    st.markdown(f"KO: {perfil_b['ko_wins']} | Sub: {perfil_b['sub_wins']} | Dec: {perfil_b['dec_wins']}")
                    st.markdown(f"Sequência: {perfil_b['win_streak']} vitórias | Títulos: {perfil_b['title_bouts']}")
                    st.markdown("**Últimas lutas**")
                    for l in lutas_b:
                        cor = "🟢" if l["resultado"] == "Vitória" else ("🔴" if l["resultado"] == "Derrota" else "🟡")
                        st.markdown(f"{cor} vs {l['adversario']} ({l['data']}) — {l['metodo']} R{l['round']}")
                    st.divider()
                    st.markdown("**Análise IA**")
                    st.info(analise_b)
                st.divider()
                st.markdown("### Previsão do modelo")
                col_p1, col_p2, col_p3 = st.columns([2, 1, 2])
                with col_p1:
                    st.metric(perfil_r["nome"], f"{prob_r}%")
                with col_p2:
                    st.markdown("<div style='text-align:center;padding-top:20px'>vs</div>", unsafe_allow_html=True)
                with col_p3:
                    st.metric(perfil_b["nome"], f"{prob_b}%")
                st.success(f"Vencedor previsto: {vencedor}")

with aba2:
    st.markdown("### Card do próximo evento — ao vivo via ESPN")
    if st.button("Atualizar card", key="refresh"):
        st.cache_data.clear()
        st.rerun()
    with st.spinner("Buscando card mais recente..."):
        df_card = buscar_card_espn()
    if df_card is None or len(df_card) == 0:
        st.error("Não foi possível buscar o card. Tente novamente.")
    else:
        evento_nome = df_card["evento"].iloc[0]
        evento_data = df_card["data"].iloc[0]
        st.markdown(f"**{evento_nome}** | {evento_data}")
        st.divider()
        for _, luta in df_card.iterrows():
            prob_r, prob_b, perfil_r, perfil_b = prever_luta_espn(luta["R_fighter"], luta["B_fighter"])
            vencedor = luta["R_fighter"] if prob_r >= prob_b else luta["B_fighter"]
            titulo = " 🏆" if luta.get("title_bout", False) else ""
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 3])
                with col1:
                    st.markdown(f"**{luta['R_fighter']}**")
                    if perfil_r:
                        st.caption(f"{perfil_r['wins']}V · {perfil_r['losses']}D | streak: {perfil_r['win_streak']}")
                    else:
                        st.caption("Dados não disponíveis")
                with col2:
                    st.markdown(f"<div style='text-align:center'><b>vs</b>{titulo}<br><small>Previsão: <b>{vencedor}</b></small></div>", unsafe_allow_html=True)
                with col3:
                    st.markdown(f"**{luta['B_fighter']}**")
                    if perfil_b:
                        st.caption(f"{perfil_b['wins']}V · {perfil_b['losses']}D | streak: {perfil_b['win_streak']}")
                    else:
                        st.caption("Dados não disponíveis")
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    st.progress(prob_r / 100, text=f"{luta['R_fighter']}: {prob_r}%")
                with col_b2:
                    st.progress(prob_b / 100, text=f"{luta['B_fighter']}: {prob_b}%")
                st.divider()
