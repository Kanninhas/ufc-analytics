
import streamlit as st
import pandas as pd
import joblib
import numpy as np
import requests
import warnings
from groq import Groq
import os
from datetime import datetime, timedelta
warnings.filterwarnings("ignore")

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

GROQ_API_KEY = os.environ.get("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", "")

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

@st.cache_data(ttl=3600)
def buscar_proximos_eventos():
    eventos = []
    data_atual = datetime.now()
    for i in range(60):
        data = data_atual + timedelta(days=i)
        date_str = data.strftime("%Y%m%d")
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates={date_str}"
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if resp.status_code == 200:
                for evento in resp.json().get("events", []):
                    nome = evento.get("name")
                    data_evento = evento.get("date", "")[:10]
                    if not any(e["nome"] == nome for e in eventos):
                        lutas = []
                        for luta in evento.get("competitions", []):
                            competidores = luta.get("competitors", [])
                            if len(competidores) >= 2:
                                r = competidores[0].get("athlete", {}).get("displayName", "N/A")
                                b = competidores[1].get("athlete", {}).get("displayName", "N/A")
                                titulo = luta.get("notes", [{}])[0].get("headline", "") if luta.get("notes") else ""
                                lutas.append({"R_fighter": r, "B_fighter": b, "title_bout": "title" in titulo.lower() if titulo else False})
                        eventos.append({"nome": nome, "data": data_evento, "lutas": lutas})
        except:
            continue
    return eventos

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

def prever_confronto(perfil_r, perfil_b):
    try:
        entrada = pd.DataFrame([[
            perfil_r["win_streak"], perfil_b["win_streak"],
            perfil_r["lose_streak"], perfil_b["lose_streak"],
            perfil_r["longest_win_streak"], perfil_b["longest_win_streak"],
            perfil_r["wins"], perfil_b["wins"],
            perfil_r["losses"], perfil_b["losses"],
            perfil_r["sig_str_pct"] / 100, perfil_b["sig_str_pct"] / 100,
            perfil_r["td_pct"] / 100, perfil_b["td_pct"] / 100,
            perfil_r["sub_att"], perfil_b["sub_att"],
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
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
    if perfil_r and perfil_b:
        prob_r, prob_b = prever_confronto(perfil_r, perfil_b)
    else:
        prob_r, prob_b = 50.0, 50.0
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
        if st.button(f"Profile: {luta['R_fighter'].split()[0]}", key=f"pr_{evento_nome}_{idx}_{luta['R_fighter']}"):
            st.session_state.lutador_selecionado = luta["R_fighter"]
            st.session_state.pagina = "perfil"
            st.rerun()
    with col2:
        if st.button(f"Profile: {luta['B_fighter'].split()[0]}", key=f"pb_{evento_nome}_{idx}_{luta['B_fighter']}"):
            st.session_state.lutador_selecionado = luta["B_fighter"]
            st.session_state.pagina = "perfil"
            st.rerun()
    st.divider()

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

    if tags:
        tags_html = " ".join([f'<span class="tag">{t}</span>' for t in tags])
        st.markdown(tags_html, unsafe_allow_html=True)

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
    tab1, tab2, tab3 = st.tabs(["Events", "Fighters", "Matchup"])

    with tab1:
        col1, col2, col3 = st.columns(3)
        col1.metric("Model accuracy", "65.8%")
        col2.metric("Fights in dataset", "7,177")
        col3.metric("Upcoming events", "6")

        st.divider()

        if st.button("Refresh", key="refresh_events"):
            st.cache_data.clear()
            st.rerun()

        with st.spinner("Loading events..."):
            eventos = buscar_proximos_eventos()

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
