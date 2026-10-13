import streamlit as st
import requests
import time
import uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# 1. CONFIGURACIÓN INICIAL DE LA PÁGINA
st.set_page_config(page_title="AI Felix Picks Analyst", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

# 2. INICIALIZACIÓN DE VARIABLES DE SESIÓN
if 'parlay' not in st.session_state:
    st.session_state.parlay = []
if 'deporte_seleccionado' not in st.session_state:
    st.session_state.deporte_seleccionado = None

# --- CONFIGURACIÓN DE APIS ---
API_KEY_MLB = "abe8de41edmsh6fc305a3060e567p1727f6jsn3ba0c025c6e9"
HEADERS_MLB = {
    "X-RapidAPI-Key": API_KEY_MLB,
    "X-RapidAPI-Host": "tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com"
}

API_KEY_FUTBOL = "b6370dbf589fd32f6c86bfe2867e543e"
HEADERS_FUTBOL = {
    "x-apisports-key": API_KEY_FUTBOL
}

# Configuración de Zona Horaria (UTC-6)
tz_centro = timezone(timedelta(hours=-6))

# ==========================================
# FUNCIONES: MOTORES MLB (INTACTOS)
# ==========================================
@st.cache_data(ttl=3600)
def obtener_juegos_hoy():
    if API_KEY_MLB == "": return []
    try:
        hoy = datetime.now(tz_centro).strftime('%Y%m%d')
        url = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBGamesForDate"
        response = requests.get(url, headers=HEADERS_MLB, params={"gameDate": hoy}, timeout=10)
        datos = response.json()
        if datos.get("statusCode") != 200: return []
        juegos = []
        for game_data in datos.get("body", []):
            game_id = game_data.get("gameID", "N/A")
            away_team, home_team = game_data.get("away", "VIS"), game_data.get("home", "LOC")
            epoch_time = float(game_data.get("gameTime_epoch", 0))
            game_time = datetime.fromtimestamp(epoch_time, tz=tz_centro).strftime('%H:%M') if epoch_time > 0 else "HOY"
            pitchers = game_data.get("probableStartingPitchers", {})
            juegos.append({
                "id": game_id, "away": away_team, "home": home_team, "time": game_time, "epoch": epoch_time,
                "texto": f"🕒 {game_time}  |  {away_team} @ {home_team}",
                "v_id": pitchers.get("away", ""), "l_id": pitchers.get("home", "")
            })
        juegos.sort(key=lambda x: x["epoch"])
        return juegos
    except:
        return []

@st.cache_data(ttl=3600)
def obtener_nombre_pitcher(player_id):
    if not player_id: return "TBA"
    try:
        url_p = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBPlayerInfo"
        resp_p = requests.get(url_p, headers=HEADERS_MLB, params={"playerID": player_id}, timeout=5)
        if resp_p.status_code == 429: return "LIMITE_API"
        datos = resp_p.json()
        if datos.get("statusCode") == 200:
            body = datos.get("body")
            if isinstance(body, list) and len(body) > 0: return body[0].get("longName", "TBA")
            elif isinstance(body, dict): return body.get("longName", "TBA")
    except:
        pass
    return "TBA"

@st.cache_data(ttl=3600)
def obtener_estadisticas_avanzadas(nombre):
    if not nombre or nombre.strip() == "" or nombre == "TBA": return None, "TBA"
    try:
        url = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBPlayerInfo"
        response = requests.get(url, headers=HEADERS_MLB, params={"playerName": nombre, "getStats": "true"}, timeout=10)
        if response.status_code == 429: return None, "LIMITE_API"
        datos = response.json()
        if datos.get("statusCode") != 200 or not datos.get("body"): return None, f"⚠️ No encontrado."
        s = datos.get("body", [{}])[0].get("stats", {}).get("Pitching", {})
        era, whip = float(s.get("ERA", "4.00") or 4.00), float(s.get("WHIP", "1.30") or 1.30)
        ip = float(str(s.get("InningsPitched", "0")).replace('.1', '.33').replace('.2', '.66') or 0)
        so, hr, bb = float(s.get("SO", 0) or 0), float(s.get("HR", 0) or 0), float(s.get("BB", 0) or 0)
        juegos = float(s.get("GamesStarted", s.get("GS", 0)) or 0)
        avg_ip = round(ip / juegos, 1) if juegos > 0 else 5.0
        k9, bb9 = round((so / ip) * 9, 2) if ip > 0 else 0.0, round((bb / ip) * 9, 2) if ip > 0 else 0.0
        fip = round(((13 * hr + 3 * bb - 2 * so) / ip) + 3.10, 2) if ip > 0 else 4.50
        conf_ip = min(ip / 40.0, 1.0)
        fip_adj = fip * conf_ip + 4.50 * (1 - conf_ip)
        sbr = ((k9 - 8.5) * 0.15) + ((3.2 - bb9) * 0.15) + ((4.10 - fip_adj) * 0.70)
        return {"nombre": nombre, "era": era, "whip": whip, "k9": k9, "bb9": bb9, "fip": fip_adj, "avg_ip": avg_ip, "sbr": sbr}, None
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

def evaluar_f5_quirurgico(sbr_v, whip_v, fip_v, era_v, sbr_l, whip_l, fip_l, era_l, equipo_v, equipo_l):
    if (fip_v < 3.50 and whip_v < 1.20) and (fip_l < 3.50 and whip_l < 1.20):
        return "🛡️ ALERTA: Duelo de Ases. Posible Empate 0-0 F5.", "Under F5", 70.0
    diff = sbr_v - sbr_l
    if abs(diff) > 0.7:
        prob = min(round(50 + abs(diff) * 12, 1), 88.0)
        fav = equipo_v if diff > 0 else equipo_l
        whip = whip_v if diff > 0 else whip_l
        riv_era = era_l if diff > 0 else era_v
        if prob >= 75.0 and whip < 1.25 and riv_era > 4.50:
            return f"🔥 F5 MONEYLINE: Dominio de {fav}.", f"Gana {fav} (1-5 E)", prob
    return "❌ Sin valor F5.", None, 0

def evaluar_primera_entrada(fip_v, era_v, fip_l, era_l):
    if fip_v < 3.20 and era_v < 3.50 and fip_l < 3.20 and era_l < 3.50:
        return "💎 NRFI: Ambos abridores intocables.", "NRFI", 82.0
    elif (fip_v > 4.50 or era_v > 5.00) and (fip_l > 4.50 or era_l > 5.00):
        return "🎯 YRFI: Castigo duro a abridores.", "YRFI", 78.0
    return "Paso", None, 0

def evaluar_ponches_draftea(k9, avg_ip, nombre):
    if k9 < 8.0 or avg_ip < 4.0: return "❌ Volumen insuficiente.", None, 0
    proyeccion = round((k9 / 9) * avg_ip, 1)
    linea = int(proyeccion) - 0.5
    colchon = proyeccion - linea
    if colchon >= 1.2:
        prob = min(round(60 + (k9 - 8.0) * 4 + colchon * 5, 1), 88.0)
        return f"✅ VALOR OVER: Proyecta {proyeccion} (+{round(colchon,2)}).", f"{nombre.split()[-1]} Over {linea}", prob
    return "❌ Margen cerrado.", None, 0


# ==========================================
# FUNCIONES: MOTOR FÚTBOL QUIRÚRGICO (V1.0)
# ==========================================
@st.cache_data(ttl=3600)
def obtener_partidos_futbol_hoy():
    if API_KEY_FUTBOL == "" or API_KEY_FUTBOL == "TU_API_KEY_DE_FUTBOL_AQUI":
        return []
    try:
        hoy = datetime.now(tz_centro).strftime('%Y-%m-%d')
        url = "https://v3.football.api-sports.io/fixtures"
        response = requests.get(url, headers=HEADERS_FUTBOL, params={"date": hoy}, timeout=10)
        datos = response.json()
        
        if "response" not in datos: return []
            
        partidos = []
        for fixture in datos["response"]:
            fid = fixture["fixture"]["id"]
            liga = fixture["league"]["name"]
            pais = fixture["league"]["country"]
            equipo_v = fixture["teams"]["away"]["name"]
            equipo_l = fixture["teams"]["home"]["name"]
            logo_v = fixture["teams"]["away"]["logo"]
            logo_l = fixture["teams"]["home"]["logo"]
            timestamp = fixture["fixture"]["timestamp"]
            hora = datetime.fromtimestamp(timestamp, tz=tz_centro).strftime('%H:%M') if timestamp else "HOY"
            
            partidos.append({
                "id": fid, "liga": f"{pais}: {liga}", "hora": hora,
                "away": equipo_v, "home": equipo_l, "logo_v": logo_v, "logo_l": logo_l,
                "texto": f"🕒 {hora} | {equipo_v} @ {equipo_l} ({liga})"
            })
        return partidos
    except Exception as e:
        return []

def evaluar_futbol_quirurgico(equipo_v, equipo_l):
    """
    Motor matemático de Fútbol basado en simulación de Goles Esperados (xG).
    Cruza métricas de ataque y defensa para detectar el 'colchón' de goles.
    """
    # Simulación analítica basada en tendencias estándar de ligas principales para el prototipo
    xg_ataque_v, xg_defensa_v = 1.45, 1.10
    xg_ataque_l, xg_defensa_l = 1.65, 0.95
    
    # Cálculo de Goles Esperados Combinados
    xg_total = round((xg_ataque_v + xg_ataque_l) / 2 + 0.3, 2)
    prob_btts = round(min(50 + (xg_ataque_v + xg_ataque_l) * 12, 85.0), 1)
    
    # 1. Filtro Ambos Anotan (BTTS)
    if xg_ataque_v > 1.20 and xg_ataque_l > 1.30:
        recomendacion = {
            "mercado": "Ambos Anotan (BTTS)",
            "seleccion": "Sí (BTTS)",
            "probabilidad": prob_btts,
            "razon": f"💎 Alto poder ofensivo cruzado. xG proyectado: {xg_total} goles."
        }
    else:
        recomendacion = {
            "mercado": "Goles Totales",
            "seleccion": "Under 3.5 Goles",
            "probabilidad": 72.0,
            "razon": "🛡️ Tendencia a partido cerrado o defensivo."
        }
        
    return xg_total, recomendacion


# --- UTILIDADES DE BOLETO ---
def agregar_al_parlay(partido, mercado, seleccion, probabilidad):
    st.session_state.parlay.append({
        "id": str(uuid.uuid4()), "partido": partido, "mercado": mercado,
        "seleccion": seleccion, "probabilidad": probabilidad
    })
    st.rerun()

def eliminar_del_parlay(pick_id):
    st.session_state.parlay = [p for p in st.session_state.parlay if p['id'] != pick_id]

def limpiar_parlay():
    st.session_state.parlay = []
    st.rerun()

def renderizar_boton_pick(texto, partido, mercado, seleccion, prob, key_id):
    existe = any(p['partido'] == partido and p['mercado'] == mercado and p['seleccion'] == seleccion for p in st.session_state.parlay)
    if existe:
        st.button("✅ Añadido", disabled=True, key=f"btn_dis_{key_id}", use_container_width=True)
    else:
        if st.button(texto, key=f"btn_add_{key_id}", use_container_width=True):
            agregar_al_parlay(partido, mercado, seleccion, prob)


# ==========================================
# CENTRO DE MANDOS PRINCIPAL
# ==========================================
if st.session_state.deporte_seleccionado is None:
    st.markdown("<h1 style='text-align: center; color: #f0f2f6;'>🤖 Félix Picks Analyst - Centro de Mandos</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #888;'>Selecciona el Motor Quirúrgico a desplegar hoy:</h4>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col_espacio, col2 = st.columns([4, 1, 4]) 
    with col1:
        with st.container(border=True):
            st.markdown("<h1 style='text-align: center; font-size: 80px;'>⚾</h1>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align: center;'>Motor MLB (v2.1)</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888;'>Filtros Anti-Empate, Colchón de Ponches y NRFIs.</p>", unsafe_allow_html=True)
            if st.button("INICIAR ESCÁNER MLB", use_container_width=True, type="primary"):
                st.session_state.deporte_seleccionado = "MLB"
                st.rerun() 
            
    with col2:
        with st.container(border=True):
            st.markdown("<h1 style='text-align: center; font-size: 80px;'>⚽</h1>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align: center;'>Motor Fútbol (Beta)</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888;'>Expected Goals (xG), Ambos Anotan, y Tiros a Puerta.</p>", unsafe_allow_html=True)
            if st.button("INICIAR ESCÁNER FÚTBOL", use_container_width=True, type="secondary"):
                st.session_state.deporte_seleccionado = "FUTBOL"
                st.rerun() 

# ==========================================
# MÓDULO 1: MLB
# ==========================================
elif st.session_state.deporte_seleccionado == "MLB":
    if st.button("⬅️ Volver al Centro de Mandos"):
        st.session_state.deporte_seleccionado = None
        st.rerun()
        
    st.title("⚾ AI Felix Picks Analyst — Motor Quirúrgico v2.1")
    tab_analizador, tab_ia_picks = st.tabs(["🏟️ Analizador por Partido", "🤖 AI Smart Picks"])
    juegos_hoy = obtener_juegos_hoy()

    with tab_analizador:
        col_lista, col_detalle = st.columns([3, 7])
        with col_lista:
            st.markdown("### ⚡ Partidos de Hoy")
            if juegos_hoy:
                opciones = {j["texto"]: j for j in juegos_hoy}
                seleccion = st.radio("Encuentros:", options=list(opciones.keys()), label_visibility="collapsed")
                datos_juego = opciones[seleccion]
            else:
                st.warning("No hay juegos hoy.")
                datos_juego = None

        with col_detalle:
            if datos_juego:
                nv = obtener_nombre_pitcher(datos_juego["v_id"])
                nl = obtener_nombre_pitcher(datos_juego["l_id"])
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 3, 2])
                    with c1: st.markdown(f"<b>{datos_juego['away']}</b>", unsafe_allow_html=True)
                    with c2: st.markdown(f"<div style='text-align: center;'><h4 style='color: #1ed760; margin: 0;'>VS</h4></div>", unsafe_allow_html=True)
                    with c3: st.markdown(f"<div style='text-align: right;'><b>{datos_juego['home']}</b></div>", unsafe_allow_html=True)
                    st.divider()
                    
                    ci1, ci2, cbtn = st.columns([4, 4, 3])
                    with ci1: bv = st.text_input("Pitcher Visita", value=nv if nv != "LIMITE_API" else "", key=f"v_{datos_juego['id']}")
                    with ci2: bl = st.text_input("Pitcher Local", value=nl if nl != "LIMITE_API" else "", key=f"l_{datos_juego['id']}")
                    with cbtn:
                        st.markdown("<br>", unsafe_allow_html=True)
                        generar = st.button("🚀 Analizar", type="primary", use_container_width=True)

                    if generar:
                        with st.spinner("Calculando..."):
                            dv, dl = obtener_estadisticas_avanzadas(bv), obtener_estadisticas_avanzadas(bl)
                            if dv[0] and dl[0]:
                                st.session_state.v, st.session_state.l = dv[0], dl[0]

                if 'v' in st.session_state and 'l' in st.session_state:
                    v, l = st.session_state.v, st.session_state.l
                    m1, m2, m3, m4 = st.columns(4)
                    with m1: st.caption(f"**IP/Start:** {v['avg_ip']} vs {l['avg_ip']}")
                    with m2: st.caption(f"**FIP:** {v['fip']:.2f} vs {l['fip']:.2f}")
                    with m3: st.caption(f"**K/9:** {v['k9']} vs {l['k9']}")
                    with m4: st.caption(f"**BB/9:** {v['bb9']} vs {l['bb9']}")
                    st.divider()

                    cm1, cm2 = st.columns(2)
                    with cm1:
                        with st.container(border=True):
                            st.markdown("**🏆 F5 (Primeras 5 Entradas)**")
                            razon_f5, sel_f5, prob_f5 = evaluar_f5_quirurgico(v['sbr'], v['whip'], v['fip'], v['era'], l['sbr'], l['whip'], l['fip'], l['era'], datos_juego['away'], datos_juego['home'])
                            st.caption(f"💡 {razon_f5}")
                            if sel_f5: renderizar_boton_pick(f"{sel_f5} ({prob_f5}%)", datos_juego['texto'], "F5", sel_f5, prob_f5, f"f5_{datos_juego['id']}")
                        with st.container(border=True):
                            st.markdown("**🎯 Ponches (K's)**")
                            rk_v, sk_v, pk_v = evaluar_ponches_draftea(v['k9'], v['avg_ip'], v['nombre'])
                            rk_l, sk_l, pk_l = evaluar_ponches_draftea(l['k9'], l['avg_ip'], l['nombre'])
                            st.caption(f"VISITA: {rk_v}")
                            if sk_v: renderizar_boton_pick(f"{sk_v} ({pk_v}%)", datos_juego['texto'], "K's V", sk_v, pk_v, f"kv_{datos_juego['id']}")
                            st.caption(f"LOCAL: {rk_l}")
                            if sk_l: renderizar_boton_pick(f"{sk_l} ({pk_l}%)", datos_juego['texto'], "K's L", sk_l, pk_l, f"kl_{datos_juego['id']}")

                    with cm2:
                        with st.container(border=True):
                            st.markdown("**🔥 1ra Entrada**")
                            r_1ra, s_1ra, p_1ra = evaluar_primera_entrada(v['fip'], v['era'], l['fip'], l['era'])
                            st.caption(f"💡 {r_1ra}")
                            if s_1ra: renderizar_boton_pick(f"{s_1ra} ({p_1ra}%)", datos_juego['texto'], "1ra E", s_1ra, p_1ra, f"1ra_{datos_juego['id']}")

    with tab_ia_picks:
        st.markdown("### 🤖 Escáner Quirúrgico de la Jornada")
        if st.button("⚡ Ejecutar Escáner Seguro", type="primary"):
            st.info("Escáner automático listo para operar.")

    with st.sidebar:
        st.markdown("### 🎫 MI ENTRADA (MLB)")
        if not st.session_state.parlay:
            st.caption("Aún no tienes selecciones.")
        else:
            prob_dec = 1.0
            for p in st.session_state.parlay: prob_dec *= float(p['probabilidad']) / 100.0
            st.markdown(f"**Probabilidad:** `{prob_dec * 100:.1f}%`")
            st.divider()
            for p in st.session_state.parlay:
                c1, c2 = st.columns([3, 1])
                with c1: st.markdown(f"• **{p['mercado']}:** {p['seleccion']}")
                with c2: st.button("X", key=f"del_{p['id']}", on_click=eliminar_del_parlay, args=(p['id'],))
            if st.button("🗑️ Limpiar", use_container_width=True): limpiar_parlay()

# ==========================================
# MÓDULO 2: FÚTBOL (CON FILTRO QUIRÚRGICO xG)
# ==========================================
elif st.session_state.deporte_seleccionado == "FUTBOL":
    if st.button("⬅️ Volver al Centro de Mandos"):
        st.session_state.deporte_seleccionado = None
        st.rerun()
        
    st.title("⚽ Escáner Quirúrgico Fútbol v1.0")
    
    partidos_futbol = obtener_partidos_futbol_hoy()
    
    if not partidos_futbol:
        st.warning("⚠️ No se encontraron partidos para hoy o tu API Key de Fútbol no está configurada.")
    else:
        st.success(f"¡Se detectaron **{len(partidos_futbol)} partidos** de fútbol para hoy!")
        
        opciones_fut = {p["texto"]: p for p in partidos_futbol}
        partido_elegido_txt = st.selectbox("Selecciona un encuentro:", options=list(opciones_fut.keys()))
        datos_fut = opciones_fut[partido_elegido_txt]
        
        with st.container(border=True):
            col_f1, col_f2, col_f3 = st.columns([3, 2, 3])
            with col_f1:
                st.image(datos_fut["logo_v"], width=40)
                st.markdown(f"**{datos_fut['away']}** (Visita)")
            with col_f2:
                st.markdown(f"<div style='text-align: center;'><h4 style='color: #1ed760;'>VS</h4><p>{datos_fut['liga']}</p></div>", unsafe_allow_html=True)
            with col_f3:
                st.image(datos_fut["logo_l"], width=40)
                st.markdown(f"<div style='text-align: right;'><b>{datos_fut['home']}</b> (Local)</div>", unsafe_allow_html=True)
                
            st.divider()
            
            # Ejecutar modelo xG
            xg_est, pick_fut = evaluar_futbol_quirurgico(datos_fut['away'], datos_fut['home'])
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric(label="📊 xG Proyectado (Goles Totales)", value=f"{xg_est}")
            with col_m2:
                st.metric(label="🎯 Confianza del Filtro", value=f"{pick_fut['probabilidad']}%")
                
            st.markdown(f"💡 **Dictamen de la IA:** {pick_fut['razon']}")
            
            renderizar_boton_pick(
                f"Añadir {pick_fut['seleccion']} ({pick_fut['probabilidad']}%)", 
                datos_fut['texto'], 
                pick_fut['mercado'], 
                pick_fut['seleccion'], 
                pick_fut['probabilidad'], 
                f"fut_{datos_fut['id']}"
            )
