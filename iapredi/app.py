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
        st.session_state.picks_mlb_ia = []
        st.session_state.ya_escaneo_mlb = False
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

def renderizar_boton_pick(texto, partido, mercado, seleccion, prob, key_id):
    if "⚠️ PASO" in seleccion:
        st.button("⚠️ No Recomendado", disabled=True, key=f"btn_paso_{key_id}", use_container_width=True)
        return
        
    existe = any(p['partido'] == partido and p['mercado'] == mercado and p['seleccion'] == seleccion for p in st.session_state.parlay)
    if existe:
        st.button("✅ Añadido", disabled=True, key=f"btn_dis_{key_id}", use_container_width=True)
    else:
        if st.button(texto, key=f"btn_add_{key_id}", use_container_width=True):
            agregar_al_parlay(partido, mercado, seleccion, prob)


# ==========================================
# FUNCIONES: MOTORES MLB (INTACTO Y BLINDADO)
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
    return "❌ Sin valor claro a Ganador F5.", None, 0

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
# FUNCIONES: MOTOR FÚTBOL REAL (IA MULTIMERCADO Y FORMA)
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
            ("England", "Premier League"), ("Spain", "La Liga"), ("Italy", "Serie A"),
            ("Germany", "Bundesliga"), ("France", "Ligue 1"), ("Mexico", "Liga MX")
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
        
        partidos.sort(key=lambda x: (x["liga"], x["hora"]))
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
    
    # Extraemos métricas base
    att_h = float(comp.get("att", {}).get("home", "50%").replace("%", ""))
    att_a = float(comp.get("att", {}).get("away", "50%").replace("%", ""))
    def_h = float(comp.get("def", {}).get("home", "50%").replace("%", ""))
    def_a = float(comp.get("def", {}).get("away", "50%").replace("%", ""))
    form_h = float(comp.get("form", {}).get("home", "50%").replace("%", ""))
    form_a = float(comp.get("form", {}).get("away", "50%").replace("%", ""))
    
    # Filtro Anti-Fantasmas
    if att_h == 50.0 and att_a == 50.0 and def_h == 50.0 and def_a == 50.0:
        return {
            "advice": "Información estadística aún no disponible en la API para este partido.",
            "moneyline": {"sel": "⚠️ PASO: API Incompleta", "prob": 0.0, "razon": "Esperar a que se acerque la hora del juego."},
            "btts": {"sel": "⚠️ PASO: API Incompleta", "prob": 0.0, "razon": "No hay comparativas reales."},
            "goals": {"sel": "⚠️ PASO: API Incompleta", "prob": 0.0, "razon": "Sin datos."},
            "shots": {"sel": "⚠️ PASO: API Incompleta", "prob": 0.0, "razon": "Sin datos."},
            "corners": {"sel": "⚠️ PASO: API Incompleta", "prob": 0.0, "razon": "Sin datos."}
        }

    p_home = float(preds.get("percent", {}).get("home", "33%").replace("%", ""))
    p_draw = float(preds.get("percent", {}).get("draw", "33%").replace("%", ""))
    p_away = float(preds.get("percent", {}).get("away", "33%").replace("%", ""))
    advice = preds.get("advice", "Sin datos concluyentes").capitalize()
    
    # 🎯 1. GANADOR (ML / DNB)
    if p_home >= 60.0 and (p_home - p_away) >= 25.0:
        ml_sel, ml_prob, ml_razon = f"Victoria Directa: {equipo_l}", round(p_home, 1), f"Dominio absoluto en casa. {equipo_l} tiene {p_home}% de probabilidad real frente a {equipo_v}."
    elif p_away >= 60.0 and (p_away - p_home) >= 25.0:
        ml_sel, ml_prob, ml_razon = f"Victoria Directa: {equipo_v}", round(p_away, 1), f"La visita es muy superior. {equipo_v} supera ampliamente las métricas de {equipo_l}."
    elif p_home >= 48.0 and (p_home - p_away) >= 15.0:
        ml_sel, ml_prob, ml_razon = f"Empate No Válido (DNB): {equipo_l}", round(p_home + (p_draw * 0.5), 1), f"{equipo_l} es superior pero hay riesgo. Reembolso si {equipo_v} logra el empate."
    elif p_away >= 48.0 and (p_away - p_home) >= 15.0:
        ml_sel, ml_prob, ml_razon = f"Empate No Válido (DNB): {equipo_v}", round(p_away + (p_draw * 0.5), 1), f"Ventaja para {equipo_v} de visita. Apuesta cubierta en caso de empate."
    else:
        favorito_real = equipo_l if p_home >= p_away else equipo_v
        ml_sel, ml_prob, ml_razon = f"⚠️ PASO: Riesgo (Sug: DNB {favorito_real})", round(max(p_home, p_away) + (p_draw * 0.5), 1), f"Juego de moneda al aire entre {equipo_l} y {equipo_v}."

    # 🎯 2. AMBOS ANOTAN (BTTS)
    pot_gol_h = (att_h + (100 - def_a)) / 2
    pot_gol_a = (att_a + (100 - def_h)) / 2
    
    if pot_gol_h >= 55.0 and pot_gol_a >= 55.0:
        btts_sel, btts_prob, btts_razon = "Ambos Anotan: SÍ", round((pot_gol_h + pot_gol_a) / 2, 1), f"Tanto {equipo_l} como {equipo_v} tienen ataques letales que superan a las defensas rivales."
    elif pot_gol_h <= 38.0 or pot_gol_a <= 38.0:
        btts_prob = round(100 - ((pot_gol_h + pot_gol_a) / 2), 1)
        if pot_gol_h <= 38.0 and pot_gol_a <= 38.0:
            btts_sel, btts_razon = "Ambos Anotan: NO", f"Ni {equipo_l} ni {equipo_v} generan peligro constante."
        elif pot_gol_h <= 38.0:
            btts_sel, btts_razon = "Ambos Anotan: NO", f"El ataque de {equipo_l} es casi nulo frente a la defensa de {equipo_v}."
        else:
            btts_sel, btts_razon = "Ambos Anotan: NO", f"El ataque de {equipo_v} batalla demasiado para anotar frente a la defensa de {equipo_l}."
    else:
        tendencia_btts = "SÍ" if (pot_gol_h + pot_gol_a) / 2 >= 50 else "NO"
        btts_sel, btts_prob, btts_razon = f"⚠️ PASO: Mercado (Sug: {tendencia_btts})", round(max((pot_gol_h + pot_gol_a) / 2, 100 - ((pot_gol_h + pot_gol_a) / 2)), 1), f"Sin tendencia clara de ataque/defensa definida."

    # 🎯 3. GOLES TOTALES
    max_ataque = max(pot_gol_h, pot_gol_a)
    suma_ataque = pot_gol_h + pot_gol_a
    equipo_power = equipo_l if pot_gol_h >= pot_gol_a else equipo_v
    
    if suma_ataque >= 135.0 or max_ataque >= 85.0:
        goles_sel, goles_prob, goles_razon = "🔥 Más de 3.5 Goles", round(min(suma_ataque * 0.55, 95.0), 1), f"Partido explosivo. {equipo_power} trae un ataque abrumador."
    elif suma_ataque >= 115.0 or max_ataque >= 72.0:
        goles_sel, goles_prob, goles_razon = "🚀 Más de 2.5 Goles", round(min(suma_ataque * 0.65, 88.0), 1), f"Alto poder ofensivo. Proyección abierta liderada por {equipo_power}."
    elif suma_ataque >= 90.0:
        goles_sel, goles_prob, goles_razon = "⚽ Más de 1.5 Goles", round(min(suma_ataque * 0.75, 85.0), 1), f"{equipo_l} y {equipo_v} deberían sumar al menos 2 goles globales."
    elif suma_ataque <= 55.0:
        goles_sel, goles_prob, goles_razon = "🧱 Menos de 1.5 Goles", round(100 - (suma_ataque * 0.8), 1), f"Juego sin ideas. Las ofensivas son inoperantes estadísticamente."
    else:
        tend_goles = "Más de 1.5 Goles" if suma_ataque >= 80.0 else "Menos de 3.5 Goles"
        goles_sel, goles_prob, goles_razon = f"⚠️ PASO (Sug: {tend_goles})", 55.0, f"El choque no arroja una línea clara de goles seguros."

    # 🎯 4. TIROS A PUERTA (Nueva Fila Matemática basada en Forma y Ataque)
    poder_tiros_h = (att_h * 0.6) + (form_h * 0.4)
    poder_tiros_a = (att_a * 0.6) + (form_a * 0.4)
    tiros_totales = (poder_tiros_h + poder_tiros_a) / 10 # Puntos promedio base
    
    if tiros_totales >= 14.5:
        shots_sel, shots_prob, shots_razon = "🔥 Más de 9.5 Tiros a Puerta", round(min(tiros_totales * 5.5, 92.0), 1), f"Asedio total. {equipo_l} y {equipo_v} vienen con jugadores en altísimo nivel de forma."
    elif tiros_totales >= 12.0:
        shots_sel, shots_prob, shots_razon = "🎯 Más de 8.5 Tiros a Puerta", round(min(tiros_totales * 6.5, 85.0), 1), f"Gran volumen de remates. Ambos equipos llegan al área con facilidad."
    elif poder_tiros_h >= 75.0 and poder_tiros_a <= 40.0:
        shots_sel, shots_prob, shots_razon = f"🎯 {equipo_l}: Más de 4.5 T. a Puerta", round(poder_tiros_h, 1), f"Monólogo local. {equipo_l} bombardeará a un {equipo_v} en mala forma."
    elif poder_tiros_a >= 75.0 and poder_tiros_h <= 40.0:
        shots_sel, shots_prob, shots_razon = f"🎯 {equipo_v}: Más de 4.5 T. a Puerta", round(poder_tiros_a, 1), f"{equipo_v} dominará los remates ante un {equipo_l} de ritmo lento."
    else:
        shots_sel, shots_prob, shots_razon = "⚠️ PASO: Tiros Inestables", 55.0, "Partido proyectado para jugarse en mediocampo sin muchos tiros limpios."

    # 🎯 5. CÓRNERS (Nueva Fila Matemática de Intensidad y Bandas)
    presion_corners = (att_h + att_a + def_h + def_a) / 4 # Alta intensidad genera bloqueos y córners
    if presion_corners >= 65.0 and (att_h > 60 or att_a > 60):
        corner_sel, corner_prob, corner_razon = "🚩 Más de 9.5 Córners", round(min(presion_corners * 1.3, 88.0), 1), f"Juego vertical asegurado. La intensidad de este cruce proyecta muchos despejes."
    elif presion_corners <= 45.0:
        corner_sel, corner_prob, corner_razon = "📉 Menos de 9.5 Córners", round(100 - presion_corners, 1), f"Equipos de posesión lenta o nulo desborde por bandas. Pocos tiros de esquina."
    else:
        corner_sel, corner_prob, corner_razon = "⚠️ PASO: Córners Lotería", 55.0, "Métricas de presión sin tendencia. Evita este mercado aquí."

    return {
        "advice": advice,
        "moneyline": {"sel": ml_sel, "prob": ml_prob, "razon": ml_razon},
        "btts": {"sel": btts_sel, "prob": btts_prob, "razon": btts_razon},
        "goals": {"sel": goles_sel, "prob": goles_prob, "razon": goles_razon},
        "shots": {"sel": shots_sel, "prob": shots_prob, "razon": shots_razon},
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
            st.markdown("<h2 style='text-align: center;'>Motor MLB (v2.2)</h2>", unsafe_allow_html=True)
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
        st.markdown(f"### 🤖 Escáner Quirúrgico ({dia_seleccionado})")
        
        if st.button(f"⚡ Escanear Mejores Picks de {dia_seleccionado}", type="primary"):
            if not juegos:
                st.warning("No hay juegos programados.")
            else:
                picks_mlb_ia = []
                barra = st.progress(0)
                status = st.empty()
                
                juegos_a_escanear = juegos[:10]
                total = len(juegos_a_escanear)
                
                for i, juego in enumerate(juegos_a_escanear):
                    status.text(f"Analizando Pitchers: {juego['away']} vs {juego['home']}...")
                    
                    nv = obtener_nombre_pitcher(juego["v_id"])
                    nl = obtener_nombre_pitcher(juego["l_id"])
                    
                    if nv != "TBA" and nl != "TBA" and nv != "LIMITE_API" and nl != "LIMITE_API":
                        dv, err_v = obtener_estadisticas_avanzadas(nv)
                        dl, err_l = obtener_estadisticas_avanzadas(nl)
                        
                        if dv and dl:
                            r_f5, s_f5, p_f5 = evaluar_f5_quirurgico(dv['sbr'], dv['whip'], dv['fip'], dv['era'], dl['sbr'], dl['whip'], dl['fip'], dl['era'], juego['away'], juego['home'])
                            if s_f5 and p_f5 >= 75.0:
                                picks_mlb_ia.append({"partido": juego['texto'], "mercado": "F5 / MITAD", "seleccion": s_f5, "probabilidad": p_f5, "razon": r_f5})
                            
                            r_1ra, s_1ra, p_1ra = evaluar_primera_entrada(dv['fip'], dv['era'], dl['fip'], dl['era'])
                            if s_1ra and p_1ra >= 75.0:
                                picks_mlb_ia.append({"partido": juego['texto'], "mercado": "1ra ENTRADA", "seleccion": s_1ra, "probabilidad": p_1ra, "razon": r_1ra})
                                
                            rk_v, sk_v, pk_v = evaluar_ponches_draftea(dv['k9'], dv['avg_ip'], dv['nombre'])
                            if sk_v and pk_v >= 75.0:
                                picks_mlb_ia.append({"partido": juego['texto'], "mercado": "PONCHES", "seleccion": sk_v, "probabilidad": pk_v, "razon": rk_v})
                                
                            rk_l, sk_l, pk_l = evaluar_ponches_draftea(dl['k9'], dl['avg_ip'], dl['nombre'])
                            if sk_l and pk_l >= 75.0:
                                picks_mlb_ia.append({"partido": juego['texto'], "mercado": "PONCHES", "seleccion": sk_l, "probabilidad": pk_l, "razon": rk_l})
                                
                    barra.progress((i + 1) / total)
                    time.sleep(1)
                
                status.text("¡Búsqueda finalizada!")
                time.sleep(0.5)
                status.empty()
                barra.empty()
                
                picks_mlb_ia.sort(key=lambda x: x['probabilidad'], reverse=True)
                st.session_state.picks_mlb_ia = picks_mlb_ia
                st.session_state.ya_escaneo_mlb = True

        if st.session_state.get("ya_escaneo_mlb", False):
            if st.session_state.picks_mlb_ia:
                st.success(f"¡El escáner encontró predicciones de pitcheo con alto valor para {dia_seleccionado.lower()}!")
                for idx, pick in enumerate(st.session_state.picks_mlb_ia):
                    with st.container(border=True):
                        cp1, cp2, cp3 = st.columns([3, 1.5, 1])
                        with cp1:
                            st.markdown(f"⚾ **{pick.get('partido', '')}**")
                            st.markdown(f"🎯 **PICK DIRECTO:** `{pick.get('seleccion', '')}`") 
                            st.caption(f"💡 *Estadística:* {pick.get('razon', '')}")
                        with cp2:
                            st.metric(label="Confianza Real", value=f"{pick.get('probabilidad', 75.0)}%")
                        with cp3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            renderizar_boton_pick("Añadir", pick.get('partido', ''), pick.get('mercado', ''), pick.get('seleccion', ''), pick.get('probabilidad', 75.0), f"mlb_ai_{idx}")


# ==========================================
# MÓDULO 2: FÚTBOL
# ==========================================
elif st.session_state.deporte_seleccionado == "FUTBOL":
    if st.button("⬅️ Volver al Centro de Mandos"):
        st.session_state.deporte_seleccionado = None
        st.rerun()
        
    st.title(f"⚽ AI Felix Picks Analyst — Fútbol ({dia_seleccionado})")
    
    tab_analizador_fut, tab_ia_picks_fut = st.tabs(["🏟️ Analizador por Partido", "🤖 AI Smart Picks"])
    partidos_futbol = obtener_partidos_futbol(offset_dias)
    
    with tab_analizador_fut:
        if not partidos_futbol:
            st.warning(f"⚠️ No hay partidos oficiales programados para {dia_seleccionado.lower()}.")
        else:
            partidos_por_liga = defaultdict(list)
            for p in partidos_futbol: 
                nombre_comp = f"{p['pais']}: {p['liga']}"
                partidos_por_liga[nombre_comp].append(p)
                
            ligas_ordenadas = sorted(partidos_por_liga.keys())
            
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
                
                if st.button("🚀 Extraer 5 Mercados de IA", type="primary", use_container_width=True):
                    with st.spinner("Cruzando Forma, Ataque y Defensa..."):
                        datos_reales = obtener_datos_reales_partido(datos_fut['id'])
                        if datos_reales:
                            st.session_state[f"analisis_{datos_fut['id']}"] = evaluar_futbol_real_api(datos_reales, datos_fut['away'], datos_fut['home'])
                        else:
                            st.error("No hay predicciones disponibles para este partido.")

                if f"analisis_{datos_fut['id']}" in st.session_state:
                    analisis = st.session_state[f"analisis_{datos_fut['id']}"]
                    
                    st.success(f"🤖 **Visión Global del Partido:** {analisis['advice']}")
                    st.divider()
                    
                    # FILA 1: Ganador, Ambos Anotan, Goles
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        with st.container(border=True):
                            st.markdown("**🏆 Línea de Dinero**")
                            st.caption(analisis['moneyline']['razon'])
                            renderizar_boton_pick(f"Añadir: {analisis['moneyline']['sel']} ({analisis['moneyline']['prob']}%)", datos_fut['texto'], "Ganador", analisis['moneyline']['sel'], analisis['moneyline']['prob'], f"ml_{datos_fut['id']}")
                    with col_m2:
                        with st.container(border=True):
                            st.markdown("**🔥 Ambos Anotan**")
                            st.caption(analisis['btts']['razon'])
                            renderizar_boton_pick(f"Añadir: {analisis['btts']['sel']} ({analisis['btts']['prob']}%)", datos_fut['texto'], "BTTS", analisis['btts']['sel'], analisis['btts']['prob'], f"btts_{datos_fut['id']}")
                    with col_m3:
                        with st.container(border=True):
                            st.markdown("**⚽ Goles Totales**")
                            st.caption(analisis['goals']['razon'])
                            renderizar_boton_pick(f"Añadir: {analisis['goals']['sel']} ({analisis['goals']['prob']}%)", datos_fut['texto'], "Goles", analisis['goals']['sel'], analisis['goals']['prob'], f"goals_{datos_fut['id']}")
                            
                    # FILA 2: Tiros a Puerta y Córners
                    col_m4, col_m5 = st.columns(2)
                    with col_m4:
                        with st.container(border=True):
                            st.markdown("**🎯 Tiros a Puerta (Forma + Ataque)**")
                            st.caption(analisis['shots']['razon'])
                            renderizar_boton_pick(f"Añadir: {analisis['shots']['sel']} ({analisis['shots']['prob']}%)", datos_fut['texto'], "Tiros a Puerta", analisis['shots']['sel'], analisis['shots']['prob'], f"shots_{datos_fut['id']}")
                    with col_m5:
                        with st.container(border=True):
                            st.markdown("**🚩 Córners (Verticalidad)**")
                            st.caption(analisis['corners']['razon'])
                            renderizar_boton_pick(f"Añadir: {analisis['corners']['sel']} ({analisis['corners']['prob']}%)", datos_fut['texto'], "Córners", analisis['corners']['sel'], analisis['corners']['prob'], f"corners_{datos_fut['id']}")

    # 🚀 ESCÁNER IA: GLOBAL O POR LIGA 🚀
    with tab_ia_picks_fut:
        st.markdown(f"### 🤖 Escáner Multimercado Inteligente ({dia_seleccionado})")
        
        if not partidos_futbol:
            st.warning("No hay partidos disponibles.")
        else:
            modo_escaneo = st.radio("Modo de Búsqueda:", ["🌍 Global (Top 15 Partidos Estelares)", "🎯 Filtrar por Liga Específica"], horizontal=True)
            
            if "Filtrar por Liga" in modo_escaneo:
                ligas_hoy = sorted(list(set([f"{p['pais']}: {p['liga']}" for p in partidos_futbol])))
                liga_filtro = st.selectbox("Selecciona la liga a escanear:", ligas_hoy)
                partidos_a_escanear = [p for p in partidos_futbol if f"{p['pais']}: {p['liga']}" == liga_filtro]
                titulo_boton = f"⚡ Escanear la {liga_filtro.split(': ')[1]}"
            else:
                partidos_a_escanear = [p for p in partidos_futbol if p['prioridad'] == 0][:15] # Top 15 Ligas Mayores
                titulo_boton = "⚡ Escanear Top Mundial"
            
            if st.button(titulo_boton, type="primary"):
                if not partidos_a_escanear:
                    st.session_state.picks_futbol_ia = []
                    st.session_state.ya_escaneo_fut = True
                else:
                    picks_futbol_ia = []
                    barra = st.progress(0)
                    status = st.empty()
                    total = len(partidos_a_escanear)
                    
                    for i, partido in enumerate(partidos_a_escanear):
                        status.text(f"Evaluando 5 Mercados de: {partido['away']} vs {partido['home']}...")
                        datos_reales = obtener_datos_reales_partido(partido['id'])
                        
                        if datos_reales:
                            res = evaluar_futbol_real_api(datos_reales, partido['away'], partido['home'])
                            # El escáner ahora busca en los 5 mercados las mejores oportunidades
                            for mercado_key, nombre_mercado in zip(['moneyline', 'btts', 'goals', 'shots', 'corners'], ['Ganador', 'BTTS', 'Goles', 'Tiros a Puerta', 'Córners']):
                                item = res[mercado_key]
                                if "⚠️ PASO" not in item['sel'] and item['prob'] >= 60.0:
                                    picks_futbol_ia.append({
                                        "partido": partido['texto'], "mercado": nombre_mercado.upper(),
                                        "seleccion": item['sel'], "probabilidad": item['prob'], "razon": item['razon']
                                    })
                        barra.progress((i + 1) / total)
                    
                    status.text("¡Escaneo Multimercado Completado!")
                    time.sleep(0.5)
                    status.empty()
                    barra.empty()
                    
                    # Ordenar por los de mayor probabilidad
                    picks_futbol_ia.sort(key=lambda x: x['probabilidad'], reverse=True)
                    st.session_state.picks_futbol_ia = picks_futbol_ia
                    st.session_state.ya_escaneo_fut = True

        if st.session_state.get("ya_escaneo_fut", False):
            if st.session_state.picks_futbol_ia:
                st.success("¡Oportunidades de Alto Valor detectadas en los 5 Mercados (Tiros, Goles, Córners y ML)!")
                for idx, pick in enumerate(st.session_state.picks_futbol_ia):
                    with st.container(border=True):
                        cp1, cp2, cp3 = st.columns([3, 1.5, 1])
                        with cp1:
                            st.markdown(f"⚽ **{pick.get('partido', '')}**")
                            st.markdown(f"🎯 **PICK DIRECTO:** `{pick.get('seleccion', '')}`") 
                            st.caption(f"💡 *IA Analítica:* {pick.get('razon', '')}")
                        with cp2:
                            st.metric(label="Confianza Real", value=f"{pick.get('probabilidad', 60.0)}%")
                        with cp3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            renderizar_boton_pick("Añadir", pick.get('partido', ''), pick.get('mercado', ''), pick.get('seleccion', ''), pick.get('probabilidad', 60.0), f"fut_ai_{idx}")
            else:
                st.info("La IA no detectó ningún pick seguro ni en tiros, goles ni ganador para esta selección. Protege tu *bankroll* y pasa el partido.")
