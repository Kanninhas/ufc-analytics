
import streamlit as st
import pandas as pd
import joblib
import numpy as np
import requests
import warnings
from groq import Groq
import os
warnings.filterwarnings("ignore")

st.set_page_config(page_title="UFC Analytics", page_icon="🥊", layout="wide")

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

def resumo_performance(lutas):
    if not lutas:
        return "Sem dados suficientes para análise de performance recente."
    vitorias = [l for l in lutas if l["resultado"] == "Vitória"]
    derrotas = [l for l in lutas if l["resultado"] == "Derrota"]
    n = len(lutas)
    nv = len(vitorias)
    nd = len(derrotas)
    metodos = [l["metodo"] for l in lutas]
    finalizacoes = sum(1 for m in metodos if "KO" in str(m) or "Submission" in str(m) or "TKO" in str(m))
    decisoes = sum(1 for m in metodos if "Decision" in str(m))
    if nv == n:
        if finalizacoes == n:
            return f"Lutador em chama — venceu todas as últimas {n} lutas por finalização. Perigoso em qualquer momento."
        elif finalizacoes > decisoes:
            return f"Excelente fase — {nv} vitórias nas últimas {n} lutas, maioria por finalização."
        else:
            return f"Dominante — {nv} vitórias nas últimas {n} lutas por decisão. Volume alto e resistência excepcional."
    elif nv > nd:
        if finalizacoes >= 1:
            return f"Boa fase com {nv} vitória(s) nas últimas {n} lutas. Mostrou capacidade de finalizar."
        else:
            return f"Fase positiva com {nv} vitória(s) nas últimas {n} lutas. Consistente e confiante."
    elif nd == n:
        return f"Momento crítico — {nd} derrotas consecutivas nas últimas {n} lutas. Precisa de reestruturação."
    elif nd > nv:
        return f"Fase difícil com {nd} derrota(s) nas últimas {n} lutas. Chega em desvantagem psicológica."
    else:
        return f"Fase irregular — resultados mistos nas últimas {n} lutas. Difícil de prever."

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

def gerar_analise_ia(perfil, lutas, resumo):
    ultimas = ""
    for l in lutas:
        ultimas += f"- {l['resultado']} vs {l['adversario']} ({l['data']}) via {l['metodo']} R{l['round']}\n"
    prompt = f"""Você é um analista especialista em MMA e UFC.
Com base nos dados abaixo, escreva uma análise curta (3-4 frases) sobre o momento atual do lutador.
Foque especialmente na performance das últimas lutas. Use linguagem de analista esportivo.

Lutador: {perfil['nome']}
Cartel: {perfil['wins']}V {perfil['losses']}D
Sequência atual: {perfil['win_streak']} vitórias / {perfil['lose_streak']} derrotas
KO/Sub/Decisão: {perfil['ko_wins']}/{perfil['sub_wins']}/{perfil['dec_wins']}
Precisão striking: {perfil['sig_str_pct']}%
Resumo recente: {resumo}

Últimas lutas:
{ultimas}

Escreva apenas a análise, sem títulos."""
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

def prever_confronto(perfil_r, perfil_b):
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
        return round(prob[1] * 100, 1), round(prob[0] * 100, 1)
    except:
        return 50.0, 50.0

def mostrar_perfil(nome):
    perfil = buscar_lutador(nome)
    if not perfil:
        st.error("Lutador não encontrado.")
        return
    lutas = ultimas_lutas(nome)
    tags = gerar_tags(perfil)
    resumo = resumo_performance(lutas)

    if st.button("Voltar", key="back"):
        st.session_state.pagina = "home"
        st.rerun()

    iniciais = "".join([p[0] for p in nome.split()[:2]]).upper()
    col_av, col_info = st.columns([1, 4])
    with col_av:
        st.markdown(f"""<div style="width:80px;height:80px;border-radius:50%;background:#FCEBEB;border:2px solid #E24B4A;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:500;color:#7F1F1F">{iniciais}</div>""", unsafe_allow_html=True)
    with col_info:
        st.markdown(f"## {perfil['nome']}")
        st.markdown(f"{perfil['altura']} · {perfil['alcance']} alcance · {perfil['peso']} · {perfil['stance']} · {perfil['idade']}")
        cols = st.columns(3)
        cols[0].metric("Vitórias", perfil["wins"])
        cols[1].metric("Derrotas", perfil["losses"])
        cols[2].metric("Títulos disputados", perfil["title_bouts"])
    if tags:
        st.markdown(" ".join([f"`{t}`" for t in tags]))

    st.divider()
    st.markdown("### Performance recente")
    vitorias_recentes = sum(1 for l in lutas if l["resultado"] == "Vitória")
    if vitorias_recentes == len(lutas):
        st.success(resumo)
    elif vitorias_recentes == 0:
        st.error(resumo)
    else:
        st.warning(resumo)

    col1, col2, col3 = st.columns(3)
    for i, luta in enumerate(lutas):
        col = [col1, col2, col3][i]
        cor = "🟢" if luta["resultado"] == "Vitória" else "🔴"
        with col:
            st.markdown(f"**{cor} vs {luta['adversario']}**")
            st.caption(f"{luta['metodo']} · R{luta['round']} · {luta['data'][:7]}")

    st.divider()
    st.markdown("### Estatísticas técnicas")
    col1, col2 = st.columns(2)
    with col1:
        st.progress(min(perfil["sig_str_pct"] / 100, 1.0), text=f"Precisão striking: {perfil['sig_str_pct']}%")
        st.progress(min(perfil["td_pct"] / 100, 1.0), text=f"Precisão takedown: {perfil['td_pct']}%")
    with col2:
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("KO/TKO", perfil["ko_wins"])
        col_b.metric("Sub", perfil["sub_wins"])
        col_c.metric("Dec", perfil["dec_wins"])
        st.markdown(f"Sequência atual: {perfil['win_streak']} vitórias | Maior: {perfil['longest_win_streak']}")

    st.divider()
    st.markdown("### Análise IA")
    with st.spinner("Gerando análise..."):
        analise = gerar_analise_ia(perfil, lutas, resumo)
    st.info(analise)

    st.divider()
    st.markdown("### Analisar confronto")
    adversario = st.selectbox("Escolha o adversário", options=["Selecione..."] + [l for l in lutadores if l.lower() != nome.lower()], key="adv_sel")
    if st.button("Analisar", type="primary", key="analisar_btn"):
        if adversario != "Selecione...":
            st.session_state.nome_r = nome
            st.session_state.nome_b = adversario
            st.session_state.pagina = "confronto"
            st.rerun()

if "pagina" not in st.session_state:
    st.session_state.pagina = "home"
if "lutador_selecionado" not in st.session_state:
    st.session_state.lutador_selecionado = None

st.markdown("## UFC Analytics")
st.markdown("Previsão de lutas com inteligência artificial")
st.divider()

if st.session_state.pagina == "perfil" and st.session_state.lutador_selecionado:
    mostrar_perfil(st.session_state.lutador_selecionado)

elif st.session_state.pagina == "confronto":
    nome_r = st.session_state.get("nome_r", "")
    nome_b = st.session_state.get("nome_b", "")
    perfil_r = buscar_lutador(nome_r)
    perfil_b = buscar_lutador(nome_b)
    if perfil_r and perfil_b:
        lutas_r = ultimas_lutas(nome_r)
        lutas_b = ultimas_lutas(nome_b)
        resumo_r = resumo_performance(lutas_r)
        resumo_b = resumo_performance(lutas_b)
        prob_r, prob_b = prever_confronto(perfil_r, perfil_b)
        vencedor = perfil_r["nome"] if prob_r > prob_b else perfil_b["nome"]

        if st.button("Voltar", key="back_conf"):
            st.session_state.pagina = "home"
            st.rerun()

        col_r, col_b = st.columns(2)
        with col_r:
            st.markdown(f"### {perfil_r['nome']}")
            vr = sum(1 for l in lutas_r if l["resultado"] == "Vitória")
            if vr == len(lutas_r):
                st.success(resumo_r)
            elif vr == 0:
                st.error(resumo_r)
            else:
                st.warning(resumo_r)
            st.markdown(f"**{perfil_r['wins']}V · {perfil_r['losses']}D** | {perfil_r['stance']} | {perfil_r['idade']}")
            st.markdown(f"Altura: {perfil_r['altura']} | Alcance: {perfil_r['alcance']}")
            st.progress(min(perfil_r["sig_str_pct"] / 100, 1.0), text=f"Striking: {perfil_r['sig_str_pct']}%")
            st.progress(min(perfil_r["td_pct"] / 100, 1.0), text=f"Takedown: {perfil_r['td_pct']}%")
            st.markdown("**Últimas lutas**")
            for l in lutas_r:
                cor = "🟢" if l["resultado"] == "Vitória" else "🔴"
                st.markdown(f"{cor} vs {l['adversario']} — {l['metodo']} R{l['round']}")
            if st.button(f"Ver perfil completo", key="perfil_r"):
                st.session_state.lutador_selecionado = nome_r
                st.session_state.pagina = "perfil"
                st.rerun()

        with col_b:
            st.markdown(f"### {perfil_b['nome']}")
            vb = sum(1 for l in lutas_b if l["resultado"] == "Vitória")
            if vb == len(lutas_b):
                st.success(resumo_b)
            elif vb == 0:
                st.error(resumo_b)
            else:
                st.warning(resumo_b)
            st.markdown(f"**{perfil_b['wins']}V · {perfil_b['losses']}D** | {perfil_b['stance']} | {perfil_b['idade']}")
            st.markdown(f"Altura: {perfil_b['altura']} | Alcance: {perfil_b['alcance']}")
            st.progress(min(perfil_b["sig_str_pct"] / 100, 1.0), text=f"Striking: {perfil_b['sig_str_pct']}%")
            st.progress(min(perfil_b["td_pct"] / 100, 1.0), text=f"Takedown: {perfil_b['td_pct']}%")
            st.markdown("**Últimas lutas**")
            for l in lutas_b:
                cor = "🟢" if l["resultado"] == "Vitória" else "🔴"
                st.markdown(f"{cor} vs {l['adversario']} — {l['metodo']} R{l['round']}")
            if st.button(f"Ver perfil completo", key="perfil_b"):
                st.session_state.lutador_selecionado = nome_b
                st.session_state.pagina = "perfil"
                st.rerun()

        st.divider()
        st.markdown("### Previsão do modelo")
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.metric(perfil_r["nome"], f"{prob_r}%")
        with col2:
            st.markdown("<div style='text-align:center;padding-top:20px'>vs</div>", unsafe_allow_html=True)
        with col3:
            st.metric(perfil_b["nome"], f"{prob_b}%")
        st.success(f"Vencedor previsto: {vencedor}")

else:
    aba1, aba2, aba3 = st.tabs(["Analisar confronto", "Perfil do lutador", "Próximo evento"])

    with aba1:
        col1, col2 = st.columns(2)
        with col1:
            nome_r = st.selectbox("Canto Vermelho", options=["Selecione..."] + lutadores, index=0, key="sel_r")
        with col2:
            nome_b = st.selectbox("Canto Azul", options=["Selecione..."] + lutadores, index=0, key="sel_b")
        if st.button("Analisar confronto", type="primary"):
            if nome_r == "Selecione..." or nome_b == "Selecione...":
                st.warning("Selecione os dois lutadores.")
            elif nome_r == nome_b:
                st.warning("Selecione lutadores diferentes.")
            else:
                st.session_state.nome_r = nome_r
                st.session_state.nome_b = nome_b
                st.session_state.pagina = "confronto"
                st.rerun()

    with aba2:
        st.markdown("Busque um lutador para ver o perfil completo com performance recente.")
        nome_busca = st.selectbox("Buscar lutador", options=["Selecione..."] + lutadores, key="busca_perfil")
        if st.button("Ver perfil", type="primary"):
            if nome_busca != "Selecione...":
                st.session_state.lutador_selecionado = nome_busca
                st.session_state.pagina = "perfil"
                st.rerun()

    with aba3:
        st.markdown("### Card do próximo evento — ao vivo via ESPN")
        if st.button("Atualizar card"):
            st.cache_data.clear()
            st.rerun()
        with st.spinner("Buscando card..."):
            df_card = buscar_card_espn()
        if df_card is None or len(df_card) == 0:
            st.error("Não foi possível buscar o card.")
        else:
            st.markdown(f"**{df_card['evento'].iloc[0]}** | {df_card['data'].iloc[0]}")
            st.divider()
            for _, luta in df_card.iterrows():
                perfil_r = buscar_lutador(luta["R_fighter"])
                perfil_b = buscar_lutador(luta["B_fighter"])
                if perfil_r and perfil_b:
                    prob_r, prob_b = prever_confronto(perfil_r, perfil_b)
                else:
                    prob_r, prob_b = 50.0, 50.0
                vencedor = luta["R_fighter"] if prob_r >= prob_b else luta["B_fighter"]
                titulo = " 🏆" if luta.get("title_bout", False) else ""
                col1, col2, col3 = st.columns([3, 2, 3])
                with col1:
                    st.markdown(f"**{luta['R_fighter']}**")
                    if perfil_r:
                        st.caption(f"{perfil_r['wins']}V · {perfil_r['losses']}D")
                    if st.button("Ver perfil", key=f"pr_{luta['R_fighter']}"):
                        st.session_state.lutador_selecionado = luta["R_fighter"]
                        st.session_state.pagina = "perfil"
                        st.rerun()
                with col2:
                    st.markdown(f"<div style='text-align:center'><b>vs</b>{titulo}<br><small>{vencedor}</small></div>", unsafe_allow_html=True)
                with col3:
                    st.markdown(f"**{luta['B_fighter']}**")
                    if perfil_b:
                        st.caption(f"{perfil_b['wins']}V · {perfil_b['losses']}D")
                    if st.button("Ver perfil", key=f"pb_{luta['B_fighter']}"):
                        st.session_state.lutador_selecionado = luta["B_fighter"]
                        st.session_state.pagina = "perfil"
                        st.rerun()
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    st.progress(prob_r / 100, text=f"{prob_r}%")
                with col_b2:
                    st.progress(prob_b / 100, text=f"{prob_b}%")
                st.divider()
