import streamlit as st
import requests
import time
import uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# 1. CONFIGURACIÓN INICIAL DE LA PÁGINA
st.set_page_config(page_title="AI Felix Picks Analyst", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

# 2. INICIALIZACIÓN DE VARIABLES Y CALENDARIO
if 'parlay' not in st.session_state:
    st.session_state.parlay = []
if 'deporte_seleccionado' not in st.session_state:
    st.session_state.deporte_seleccionado = None
if 'last_offset' not in st.session_state:
    st.session_state.last_offset = 0

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

tz_centro = timezone(timedelta(hours=-6))

# ==========================================
# BARRA LATERAL: CALENDARIO Y BOLETO
# ==========================================
with st.sidebar:
    st.markdown("### 📅 CALENDARIO DE APUESTAS")
    dias_opciones = {"Hoy": 0, "Mañana": 1, "Pasado Mañana": 2}
    dia_seleccionado = st.radio("Selecciona la fecha de los juegos:", list(dias_opciones.keys()))
    offset_dias = dias_opciones[dia_seleccionado]
    
    if st.session_state.last_offset != offset_dias:
        st.session_state.picks_futbol_ia = []
        st.session_state.ya_escaneo_fut = False
        st.session_state.last_offset = offset_dias
        st.rerun()
        
    st.divider()
    st.markdown("### 🎫 MI ENTRADA MULTIDEPORTE")
    if not st.session_state.parlay:
        st.caption("Aún no tienes selecciones en tu boleto.")
    else:
        prob_dec = 1.0
        for p in st.session_state.parlay: 
            prob_dec *= float(p['probabilidad']) / 100.0
            
        prob_porcentaje = prob_dec * 100
        dec_odds = 1 / prob_dec if prob_dec > 0 else 1.0
        
        c_p, c_m = st.columns(2)
        with c_p: st.markdown(f"**Probabilidad Real**\n\n`{prob_porcentaje:.1f}%`")
        with c_m: st.markdown(f"**Momio Justo**\n\n`{dec_odds:.2f}x`")
        
        st.divider()
        
        parlay_por_partido = defaultdict(list)
        for pick in st.session_state.parlay:
            parlay_por_partido[pick['partido']].append(pick)
            
        for partido, picks in parlay_por_partido.items():
            with st.container(border=True):
                st.markdown(f"📌 **{partido}**")
                for p in picks:
                    col_t, col_b = st.columns([75, 25])
                    with col_t:
                        st.markdown(f"• **{p['mercado']}:**\n{p['seleccion']} ({p['probabilidad']}%)")
                    with col_b:
                        st.button("X", key=f"del_{p['id']}", on_click=lambda pid=p['id']: eliminar_del_parlay(pid), use_container_width=True)
        
        st.divider()
        if st.button("🗑️ Limpiar Boleto", type="secondary", use_container_width=True):
            st.session_state.parlay = []
            st.rerun()

def eliminar_del_parlay(pick_id):
    st.session_state.parlay = [p for p in st.session_state.parlay if p['id'] != pick_id]

def agregar_al_parlay(partido, mercado, seleccion, probabilidad):
    st.session_state.parlay.append({
        "id": str(uuid.uuid4()), "partido": partido, "mercado": mercado,
        "seleccion": seleccion, "probabilidad": probabilidad
    })
    st.rerun()

# --- AQUÍ DESBLOQUEAMOS EL BOTÓN DE AÑADIR SIEMPRE ---
def renderizar_boton_pick(texto, partido, mercado, seleccion, prob, key_id):
    existe = any(p['partido'] == partido and p['mercado'] == mercado and p['seleccion'] == seleccion for p in st.session_state.parlay)
    if existe:
        st.button("✅ Añadido", disabled=True, key=f"btn_dis_{key_id}", use_container_width=True)
    else:
        if st.button(texto, key=f"btn_add_{key_id}", use_container_width=True):
            agregar_al_parlay(partido, mercado, seleccion, prob)


# ==========================================
# FUNCIONES: MOTORES MLB
# ==========================================
@st.cache_data(ttl=3600)
def obtener_juegos_mlb(offset_dias):
    if API_KEY_MLB == "": return []
    try:
        fecha_obj = datetime.now(tz_centro) + timedelta(days=offset_dias)
        fecha_str = fecha_obj.strftime('%Y%m%d')
        url = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBGamesForDate"
        response = requests.get(url, headers=HEADERS_MLB, params={"gameDate": fecha_str}, timeout=10)
        datos = response.json()
        if datos.get("statusCode") != 200: return []
        juegos = []
        for game_data in datos.get("body", []):
            game_id = game_data.get("gameID", "N/A")
            away_team, home_team = game_data.get("away", "VIS"), game_data.get("home", "LOC")
            epoch_time = float(game_data.get("gameTime_epoch", 0))
            game_time = datetime.fromtimestamp(epoch_time, tz=tz_centro).strftime('%H:%M') if epoch_time > 0 else "N/A"
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
# FUNCIONES: MOTOR FÚTBOL REAL (SIN MAQUILLAJE)
# ==========================================
@st.cache_data(ttl=3600)
def obtener_partidos_futbol(offset_dias):
    if API_KEY_FUTBOL == "" or API_KEY_FUTBOL == "TU_API_KEY_DE_FUTBOL_AQUI": return []
    try:
        fecha_obj = datetime.now(tz_centro) + timedelta(days=offset_dias)
        fecha_str = fecha_obj.strftime('%Y-%m-%d')
        url = "https://v3.football.api-sports.io/fixtures"
        response = requests.get(url, headers=HEADERS_FUTBOL, params={"date": fecha_str, "timezone": "America/Mexico_City"}, timeout=10)
        datos = response.json()
        if "response" not in datos or not datos["response"]: return []
            
        ligas_top_nacionales = {
            ("England", "Premier League"),
            ("Spain", "La Liga"),
            ("Italy", "Serie A"),
            ("Germany", "Bundesliga"),
            ("France", "Ligue 1"),
            ("Mexico", "Liga MX")
        }
        ligas_top_internacionales = ["UEFA Champions League", "Copa Libertadores", "CONMEBOL Sudamericana", "UEFA Europa League"]
            
        partidos = []
        for fixture in datos["response"]:
            fid = fixture["fixture"]["id"]
            liga = fixture["league"]["name"]
            pais = fixture["league"]["country"]
            equipo_v = fixture["teams"]["away"]["name"]
            equipo_l = fixture["teams"]["home"]["name"]
            
            es_top = (pais, liga) in ligas_top_nacionales or liga in ligas_top_internacionales
            prioridad = 0 if es_top else 1
            hora = datetime.fromtimestamp(fixture["fixture"]["timestamp"], tz=tz_centro).strftime('%H:%M') if fixture["fixture"]["timestamp"] else "N/A"
            
            partidos.append({
                "id": fid, "liga": liga, "pais": pais, "hora": hora, "prioridad": prioridad,
                "away": equipo_v, "home": equipo_l, "logo_v": fixture["teams"]["away"]["logo"], "logo_l": fixture["teams"]["home"]["logo"],
                "texto": f"[{liga}] 🕒 {hora} | {equipo_v} @ {equipo_l}"
            })
        partidos.sort(key=lambda x: (x["prioridad"], x["liga"]))
        return partidos
    except:
        return []

@st.cache_data(ttl=3600)
def obtener_datos_reales_partido(fixture_id):
    url = "https://v3.football.api-sports.io/predictions"
    try:
        response = requests.get(url, headers=HEADERS_FUTBOL, params={"fixture": fixture_id}, timeout=10)
        if response.status_code == 429: return None 
        datos = response.json()
        if "response" in datos and len(datos["response"]) > 0:
            return datos["response"][0]
        return None
    except:
        return None

def evaluar_futbol_real_api(datos_api, equipo_v, equipo_l):
    preds = datos_api.get("predictions", {})
    comp = datos_api.get("comparison", {})
    
    p_home = float(preds.get("percent", {}).get("home", "33%").replace("%", ""))
    p_draw = float(preds.get("percent", {}).get("draw", "33%").replace("%", ""))
    p_away = float(preds.get("percent", {}).get("away", "33%").replace("%", ""))
    advice = preds.get("advice", "Sin datos concluyentes").capitalize()
    
    # 🎯 EVALUACIÓN ESTRICTA DE GANADOR
    if p_home >= 60.0 and (p_home - p_away) >= 25.0:
        ml_sel = f"Victoria Directa: {equipo_l}"
        ml_prob = round(p_home, 1)
        ml_razon = f"Dominio claro de {equipo_l} ({p_home}% de probabilidad real)."
    elif p_away >= 60.0 and (p_away - p_home) >= 25.0:
        ml_sel = f"Victoria Directa: {equipo_v}"
        ml_prob = round(p_away, 1)
        ml_razon = f"Dominio claro de {equipo_v} ({p_away}% de probabilidad real)."
    elif p_home >= 48.0 and (p_home - p_away) >= 15.0:
        ml_sel = f"Empate No Válido (DNB): {equipo_l}"
        ml_prob = round(p_home + (p_draw * 0.5), 1)
        ml_razon = f"Ventaja para {equipo_l}. Si empatan, se reembolsa la apuesta."
    elif p_away >= 48.0 and (p_away - p_home) >= 15.0:
        ml_sel = f"Empate No Válido (DNB): {equipo_v}"
        ml_prob = round(p_away + (p_draw * 0.5), 1)
        ml_razon = f"Ventaja para {equipo_v}. Si empatan, se reembolsa la apuesta."
    else:
        # --- NUEVA LÓGICA: Da la alerta pero MUESTRA el pick sugerido ---
        favorito_real = equipo_l if p_home >= p_away else equipo_v
        ml_sel = f"⚠️ PASO: Partido Trampa / Sin Valor (Sugerencia: DNB {favorito_real})"
        ml_prob = round(max(p_home, p_away) + (p_draw * 0.5), 1)
        ml_razon = "Probabilidades muy divididas. Riesgo alto, decisión del usuario."

    # 🎯 EVALUACIÓN DE AMBOS ANOTAN (BTTS)
    att_h = float(comp.get("att", {}).get("home", "50%").replace("%", ""))
    att_a = float(comp.get("att", {}).get("away", "50%").replace("%", ""))
    def_h = float(comp.get("def", {}).get("home", "50%").replace("%", ""))
    def_a = float(comp.get("def", {}).get("away", "50%").replace("%", ""))
    
    potencial_goles_h = (att_h + (100 - def_a)) / 2
    potencial_goles_a = (att_a + (100 - def_h)) / 2
    
    if potencial_goles_h >= 55.0 and potencial_goles_a >= 55.0:
        btts_sel = "Ambos Equipos Anotan: SÍ"
        btts_prob = round((potencial_goles_h + potencial_goles_a) / 2, 1)
        btts_razon = "Ambas ofensivas superan claramente a las defensas rivales."
    elif potencial_goles_h <= 38.0 or potencial_goles_a <= 38.0:
        btts_sel = "Ambos Equipos Anotan: NO"
        btts_prob = round(100 - ((potencial_goles_h + potencial_goles_a) / 2), 1)
        btts_razon = "Al menos un equipo tiene ataque nulo o defensa impenetrable."
    else:
        # --- NUEVA LÓGICA: Da la alerta pero MUESTRA el pick sugerido ---
        tendencia_btts = "SÍ" if (potencial_goles_h + potencial_goles_a) / 2 >= 50 else "NO"
        btts_sel = f"⚠️ PASO: Partido Trampa / Sin Valor (Sugerencia: {tendencia_btts})"
        btts_prob = round(max((potencial_goles_h + potencial_goles_a) / 2, 100 - ((potencial_goles_h + potencial_goles_a) / 2)), 1)
        btts_razon = "Métricas sin tendencia clara. Decisión del usuario."

    # 🎯 EVALUACIÓN DE GOLES (OVER/UNDER)
    max_ataque = max(potencial_goles_h, potencial_goles_a)
    suma_ataque = potencial_goles_h + potencial_goles_a
    
    if max_ataque >= 65.0 and suma_ataque >= 115.0:
        corner_sel = "Más de 2.5 Goles Totales"
        corner_prob = round(max_ataque, 1)
        corner_razon = "Poder ofensivo muy elevado. Proyección de partido abierto."
    elif suma_ataque >= 95.0:
        corner_sel = "Más de 1.5 Goles Totales"
        corner_prob = round(min(suma_ataque * 0.7, 88.0), 1)
        corner_razon = "Partido con alta probabilidad de al menos 2 goles globales."
    elif suma_ataque <= 65.0:
        corner_sel = "Menos de 2.5 Goles Totales"
        corner_prob = round(100 - (suma_ataque / 2), 1)
        corner_razon = "Equipos defensivos o de muy bajo promedio de gol."
    else:
        # --- NUEVA LÓGICA: Da la alerta pero MUESTRA el pick sugerido ---
        tend_goles = "Más de 1.5 Goles Totales" if suma_ataque >= 75.0 else "Menos de 3.5 Goles Totales"
        corner_sel = f"⚠️ PASO: Partido Trampa / Sin Valor (Sugerencia: {tend_goles})"
        corner_prob = round(max(suma_ataque * 0.5, 100 - (suma_ataque * 0.5)), 1)
        corner_razon = "Línea de goles sin valor sólido. Decisión del usuario."

    return {
        "advice": advice,
        "moneyline": {"sel": ml_sel, "prob": ml_prob, "razon": ml_razon},
        "btts": {"sel": btts_sel, "prob": btts_prob, "razon": btts_razon},
        "corners": {"sel": corner_sel, "prob": corner_prob, "razon": corner_razon}
    }


# ==========================================
# CENTRO DE MANDOS PRINCIPAL
# ==========================================
if st.session_state.deporte_seleccionado is None:
    st.markdown("<h1 style='text-align: center; color: #f0f2f6;'>🤖 Félix Picks Analyst - Centro de Mandos</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #888;'>Selecciona el Motor Quirúrgico a desplegar:</h4>", unsafe_allow_html=True)
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
            st.markdown("<h2 style='text-align: center;'>Motor Fútbol (Datos Reales)</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888;'>Conectado a la base de predicciones y estadísticas oficiales.</p>", unsafe_allow_html=True)
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
        
    st.title(f"⚾ AI Felix Picks Analyst — MLB ({dia_seleccionado})")
    tab_analizador, tab_ia_picks = st.tabs(["🏟️ Analizador por Partido", "🤖 AI Smart Picks"])
    juegos = obtener_juegos_mlb(offset_dias)

    with tab_analizador:
        col_lista, col_detalle = st.columns([3, 7])
        with col_lista:
            st.markdown(f"### ⚡ Partidos ({dia_seleccionado})")
            if juegos:
                opciones = {j["texto"]: j for j in juegos}
                seleccion = st.radio("Encuentros:", options=list(opciones.keys()), label_visibility="collapsed")
                datos_juego = opciones[seleccion]
            else:
                st.warning("No hay juegos programados.")
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
        st.markdown("### 🤖 Escáner Quirúrgico")
        st.info("Función de escáner en mantenimiento para MLB.")

# ==========================================
# MÓDULO 2: FÚTBOL
# ==========================================
elif st.session_state.deporte_seleccionado == "FUTBOL":
    if st.button("⬅️ Volver al Centro de Mandos"):
        st.session_state.deporte_seleccionado = None
        st.rerun()
        
    st.title(f"⚽ AI Felix Picks Analyst — Fútbol ({dia_seleccionado})")
    
    tab_analizador_fut, tab_ia_picks_fut = st.tabs(["🏟️ Analizador por Partido", "🤖 AI Smart Picks (Ligas Top)"])
    partidos_futbol = obtener_partidos_futbol(offset_dias)
    
    with tab_analizador_fut:
        if not partidos_futbol:
            st.warning(f"⚠️ No hay partidos oficiales programados para {dia_seleccionado.lower()}.")
        else:
            partidos_por_liga = defaultdict(list)
            prioridad_liga = {}
            for p in partidos_futbol: 
                nombre_comp = f"{p['pais']}: {p['liga']}"
                partidos_por_liga[nombre_comp].append(p)
                prioridad_liga[nombre_comp] = p['prioridad']
                
            ligas_ordenadas = sorted(partidos_por_liga.keys(), key=lambda x: (prioridad_liga[x], x))
            
            liga_seleccionada = st.selectbox("🏆 Selecciona una Competición:", options=ligas_ordenadas)
            partidos_de_liga = partidos_por_liga[liga_seleccionada]
            opciones_fut = {p["texto"]: p for p in partidos_de_liga}
            
            partido_elegido_txt = st.selectbox("⚽ Selecciona el Encuentro:", options=list(opciones_fut.keys()))
            datos_fut = opciones_fut[partido_elegido_txt]
            
            with st.container(border=True):
                col_f1, col_f2, col_f3 = st.columns([3, 2, 3])
                with col_f1:
                    st.image(datos_fut["logo_v"], width=40)
                    st.markdown(f"**{datos_fut['away']}**")
                with col_f2:
                    st.markdown(f"<div style='text-align: center;'><h4 style='color: #1ed760;'>VS</h4><p>{datos_fut['liga']}</p></div>", unsafe_allow_html=True)
                with col_f3:
                    st.image(datos_fut["logo_l"], width=40)
                    st.markdown(f"<div style='text-align: right;'><b>{datos_fut['home']}</b></div>", unsafe_allow_html=True)
                    
                st.divider()
                
                if st.button("🚀 Extraer Pronóstico Directo (API)", type="primary", use_container_width=True):
                    with st.spinner("Descargando análisis oficial..."):
                        datos_reales = obtener_datos_reales_partido(datos_fut['id'])
                        if datos_reales:
                            st.session_state[f"analisis_{datos_fut['id']}"] = evaluar_futbol_real_api(datos_reales, datos_fut['away'], datos_fut['home'])
                        else:
                            st.error("No hay predicciones disponibles para este partido.")

                if f"analisis_{datos_fut['id']}" in st.session_state:
                    analisis = st.session_state[f"analisis_{datos_fut['id']}"]
                    
                    st.success(f"🤖 **Consejo Central:** {analisis['advice']}")
                    st.divider()
                    
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        with st.container(border=True):
                            st.markdown("**🏆 Línea de Dinero**")
                            st.caption(analisis['moneyline']['razon'])
                            renderizar_boton_pick(
                                f"Añadir: {analisis['moneyline']['sel']} ({analisis['moneyline']['prob']}%)",
                                datos_fut['texto'], "Ganador", analisis['moneyline']['sel'], analisis['moneyline']['prob'], f"ml_{datos_fut['id']}"
                            )
                    with col_m2:
                        with st.container(border=True):
                            st.markdown("**🔥 Ambos Anotan**")
                            st.caption(analisis['btts']['razon'])
                            renderizar_boton_pick(
                                f"Añadir: {analisis['btts']['sel']} ({analisis['btts']['prob']}%)",
                                datos_fut['texto'], "BTTS", analisis['btts']['sel'], analisis['btts']['prob'], f"btts_{datos_fut['id']}"
                            )
                    with col_m3:
                        with st.container(border=True):
                            st.markdown("**🚩 Acción (Goles/Corners)**")
                            st.caption(analisis['corners']['razon'])
                            renderizar_boton_pick(
                                f"Añadir: {analisis['corners']['sel']} ({analisis['corners']['prob']}%)",
                                datos_fut['texto'], "Over/Under", analisis['corners']['sel'], analisis['corners']['prob'], f"corner_{datos_fut['id']}"
                            )

    with tab_ia_picks_fut:
        st.markdown(f"### 🤖 Escáner de Ligas Top ({dia_seleccionado})")
        st.markdown("Busca únicamente apuestas con alto valor estadístico real (sin inflar porcentajes).")
        
        if st.button(f"⚡ Escanear Mejores Picks de {dia_seleccionado}", type="primary"):
            if not partidos_futbol:
                st.warning("No hay partidos disponibles.")
            else:
                partidos_top = [p for p in partidos_futbol if p['prioridad'] == 0][:10]
                
                if not partidos_top:
                    st.session_state.picks_futbol_ia = []
                    st.session_state.ya_escaneo_fut = True
                else:
                    picks_futbol_ia = []
                    barra = st.progress(0)
                    status = st.empty()
                    total = len(partidos_top)
                    
                    for i, partido in enumerate(partidos_top):
                        status.text(f"Analizando: {partido['away']} vs {partido['home']}...")
                        datos_reales = obtener_datos_reales_partido(partido['id'])
                        
                        if datos_reales:
                            res = evaluar_futbol_real_api(datos_reales, partido['away'], partido['home'])
                            for mercado_key in ['moneyline', 'btts', 'corners']:
                                item = res[mercado_key]
                                if "⚠️ PASO" not in item['sel'] and item['prob'] >= 60.0:
                                    picks_futbol_ia.append({
                                        "partido": partido['texto'], "mercado": mercado_key.upper(),
                                        "seleccion": item['sel'], "probabilidad": item['prob'], "razon": item['razon']
                                    })
                        barra.progress((i + 1) / total)
                    
                    status.text("¡Búsqueda finalizada!")
                    time.sleep(0.5)
                    status.empty()
                    barra.empty()
                    
                    picks_futbol_ia.sort(key=lambda x: x['probabilidad'], reverse=True)
                    st.session_state.picks_futbol_ia = picks_futbol_ia
                    st.session_state.ya_escaneo_fut = True

        if st.session_state.get("ya_escaneo_fut", False):
            if st.session_state.picks_futbol_ia:
                st.success(f"¡El escáner filtró jugadas de VALOR REAL (sin falsos 90%) para {dia_seleccionado.lower()}!")
                for idx, pick in enumerate(st.session_state.picks_futbol_ia):
                    with st.container(border=True):
                        cp1, cp2, cp3 = st.columns([3, 1.5, 1])
                        with cp1:
                            st.markdown(f"⚽ **{pick.get('partido', '')}**")
                            st.markdown(f"🎯 **PICK DIRECTO:** `{pick.get('seleccion', '')}`") 
                            st.caption(f"💡 *Justificación:* {pick.get('razon', '')}")
                        with cp2:
                            st.metric(label="Confianza Real", value=f"{pick.get('probabilidad', 60.0)}%")
                        with cp3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            renderizar_boton_pick("Añadir", pick.get('partido', ''), pick.get('mercado', ''), pick.get('seleccion', ''), pick.get('probabilidad', 60.0), f"fut_ai_{idx}")
            else:
                st.info(f"Para {dia_seleccionado.lower()} no hay apuestas de alto valor seguro. La IA recomienda PASAR en la jornada.")
