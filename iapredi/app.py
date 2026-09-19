import streamlit as st
import requests
import time
import uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict

st.set_page_config(page_title="AI Felix Picks Analyst", page_icon="⚾", layout="wide")

if 'parlay' not in st.session_state:
    st.session_state.parlay = []

# --- 1. CONFIGURACIÓN DE API ---
API_KEY = "d0aa1d0b3amshb444051e088b6aep120b53jsndf0cdf41fcff" 
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com"
}

# Configuración de Zona Horaria (UTC-6)
tz_centro = timezone(timedelta(hours=-6))

# --- 2. MOTORES DE EXTRACCIÓN Y SABERMETRÍA ---

@st.cache_data(ttl=3600)
def obtener_juegos_hoy():
    if API_KEY == "" or API_KEY == "TU_API_KEY_AQUI":
        return []
        
    try:
        hoy = datetime.now(tz_centro).strftime('%Y%m%d')
        url = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBGamesForDate"
        
        response = requests.get(url, headers=HEADERS, params={"gameDate": hoy}, timeout=10)
        datos = response.json()
        
        if datos.get("statusCode") != 200:
            return []
            
        juegos = []
        body = datos.get("body", [])
        
        for game_data in body:
            game_id = game_data.get("gameID", "N/A")
            away_team = game_data.get("away", "VIS")
            home_team = game_data.get("home", "LOC")
            epoch_time = float(game_data.get("gameTime_epoch", 0))
            
            if epoch_time > 0:
                game_time = datetime.fromtimestamp(epoch_time, tz=tz_centro).strftime('%H:%M')
            else:
                game_time = game_data.get("gameTime", "HOY")
            
            pitchers = game_data.get("probableStartingPitchers", {})
            away_id = pitchers.get("away", "")
            home_id = pitchers.get("home", "")
            
            # Capturamos datos contextuales del equipo si vienen en la API
            texto_formato = f"🕒 {game_time}  |  {away_team} @ {home_team}"
            
            juegos.append({
                "id": game_id,
                "away": away_team,
                "home": home_team,
                "time": game_time,
                "epoch": epoch_time,
                "texto": texto_formato,
                "v_id": away_id,
                "l_id": home_id
            })
                
        juegos.sort(key=lambda x: x["epoch"])
        return juegos
    except Exception as e:
        return []

@st.cache_data(ttl=3600)
def obtener_nombre_pitcher(player_id):
    if not player_id: 
        return "TBA"
    try:
        url_p = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBPlayerInfo"
        resp_p = requests.get(url_p, headers=HEADERS, params={"playerID": player_id}, timeout=5).json()
        
        if resp_p.get("statusCode") == 200:
            body = resp_p.get("body")
            if isinstance(body, list) and len(body) > 0:
                return body[0].get("longName", "TBA")
            elif isinstance(body, dict):
                return body.get("longName", "TBA")
    except:
        pass
    return "TBA"

def obtener_estadisticas_avanzadas(nombre):
    if not nombre or nombre.strip() == "" or nombre == "TBA":
        return None, f"Pitcher '{nombre}' no confirmado."
        
    try:
        url = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBPlayerInfo"
        response = requests.get(url, headers=HEADERS, params={"playerName": nombre, "getStats": "true"}, timeout=10)
        datos = response.json()
        
        if datos.get("statusCode") != 200 or not datos.get("body"):
            return None, f"⚠️ No encontrado: '{nombre}'."
            
        jugador_data = datos.get("body", [{}])[0]
        nombre_real = jugador_data.get("longName", nombre)
        stats_root = jugador_data.get("stats", {})
        
        s = stats_root.get("Pitching", stats_root)
            
        era = float(s.get("ERA", "4.00") or 4.00)
        whip = float(s.get("WHIP", "1.30") or 1.30)
        ip = float(str(s.get("InningsPitched", "0")).replace('.1', '.33').replace('.2', '.66') or 0)
        so = float(s.get("SO", s.get("strikeouts", "0")) or 0)
        hr = float(s.get("HR", "0") or 0)
        bb = float(s.get("BB", "0") or 0)
        
        k9 = round((so / ip) * 9, 2) if ip > 0 else 0.0
        bb9 = round((bb / ip) * 9, 2) if ip > 0 else 0.0
        fip = round(((13 * hr + 3 * bb - 2 * so) / ip) + 3.10, 2) if ip > 0 else 4.50
        
        confianza_ip = min(ip / 40.0, 1.0)
        fip_ajustado = fip * confianza_ip + 4.50 * (1 - confianza_ip)
        
        # SBR Base del Abridor
        sbr_poder = ((k9 - 8.5) * 0.15) + ((3.2 - bb9) * 0.15) + ((4.10 - fip_ajustado) * 0.70)
        
        return {
            "nombre": nombre_real, 
            "era": era, 
            "whip": whip, 
            "k9": k9, 
            "bb9": bb9,
            "fip": fip_ajustado, 
            "ip": ip,
            "sbr": sbr_poder
        }, None
        
    except Exception as e:
        return None, f"❌ Error extrayendo datos: {str(e)}"

# --- 3. FUNCIONES DEL BOLETO ---
def agregar_al_parlay(partido, mercado, seleccion, probabilidad):
    st.session_state.parlay.append({
        "id": str(uuid.uuid4()),
        "partido": partido,
        "mercado": mercado,
        "seleccion": seleccion,
        "probabilidad": probabilidad
    })
    st.rerun()

def eliminar_del_parlay(pick_id):
    st.session_state.parlay = [p for p in st.session_state.parlay if p['id'] != pick_id]

def limpiar_parlay():
    st.session_state.parlay = []
    st.rerun()

# --- 4. INTERFAZ PRINCIPAL ---
st.title("⚾ AI Felix Picks Analyst — Motor Quirúrgico Híbrido")

tab_analizador, tab_ia_picks = st.tabs(["🏟️ Analizador por Partido", "🤖 AI Smart Picks (Escáner Híbrido)"])

juegos_hoy = obtener_juegos_hoy()

# ==========================================
# PESTAÑA 1: ANALIZADOR INDIVIDUAL
# ==========================================
with tab_analizador:
    col_lista, col_detalle = st.columns([3, 7])

    with col_lista:
        st.markdown("### ⚡ Partidos de Hoy")
        if juegos_hoy:
            opciones_juegos = {j["texto"]: j for j in juegos_hoy}
            juego_seleccionado = st.radio("Encuentros:", options=list(opciones_juegos.keys()), label_visibility="collapsed")
            datos_juego = opciones_juegos[juego_seleccionado]
        else:
            st.warning("No hay juegos hoy o la API está actualizando.")
            datos_juego = None

    with col_detalle:
        if datos_juego:
            nombre_v_inicial = obtener_nombre_pitcher(datos_juego["v_id"])
            nombre_l_inicial = obtener_nombre_pitcher(datos_juego["l_id"])
            
            away_team = datos_juego["away"]
            home_team = datos_juego["home"]
            game_time = datos_juego["time"]
            
            logo_away = f"https://a.espncdn.com/i/teamlogos/mlb/500/{away_team.lower()}.png"
            logo_home = f"https://a.espncdn.com/i/teamlogos/mlb/500/{home_team.lower()}.png"
            
            with st.container(border=True):
                col_lg1, col_info, col_lg2 = st.columns([2, 3, 2])
                with col_lg1:
                    st.image(logo_away, width=35)
                    st.markdown(f"<div style='text-align: left;'><b>{away_team}</b> <span style='font-size: 11px; color: gray;'>Visita</span></div>", unsafe_allow_html=True)
                with col_info:
                    st.markdown(f"<div style='text-align: center;'><h4 style='color: #1ed760; margin: 0;'>VS</h4><p style='margin: 0; font-size: 13px;'>🕒 {game_time}</p></div>", unsafe_allow_html=True)
                with col_lg2:
                    st.image(logo_home, width=35)
                    st.markdown(f"<div style='text-align: right;'><b>{home_team}</b> <span style='font-size: 11px; color: gray;'>Local</span></div>", unsafe_allow_html=True)
                
                st.divider()
                
                c_inf1, c_inf2, c_btn = st.columns([4, 4, 3])
                with c_inf1: 
                    busqueda_v = st.text_input(f"Pitcher Visita", value=nombre_v_inicial, key=f"v_{datos_juego['id']}")
                with c_inf2: 
                    busqueda_l = st.text_input(f"Pitcher Local", value=nombre_l_inicial, key=f"l_{datos_juego['id']}")
                with c_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    generar = st.button("🚀 Analizar", type="primary", use_container_width=True)

                if generar:
                    with st.spinner("Calculando rating híbrido (Pitcheo + Ofensiva)..."):
                        datos_v, err_v = obtener_estadisticas_avanzadas(busqueda_v)
                        datos_l, err_l = obtener_estadisticas_avanzadas(busqueda_l)
                        
                        if err_v: st.error(err_v)
                        if err_l: st.error(err_l)
                        
                        if datos_v and datos_l:
                            st.session_state.v = datos_v
                            st.session_state.l = datos_l

            if 'v' in st.session_state:
                v = st.session_state.v
                l = st.session_state.l
                
                m1, m2, m3, m4 = st.columns(4)
                with m1: st.caption(f"**IP:** {v['ip']} vs {l['ip']}")
                with m2: st.caption(f"**FIP:** {v['fip']:.2f} vs {l['fip']:.2f}")
                with m3: st.caption(f"**K/9:** {v['k9']} vs {l['k9']}")
                with m4: st.caption(f"**BB/9:** {v['bb9']} vs {l['bb9']}")
                
                st.divider()

                col_m1, col_m2 = st.columns(2)
                
                with col_m1:
                    with st.container(border=True):
                        st.markdown("**🏆 Ganador (ML Híbrido)**")
                        
                        # Bonificación por factor ofensivo de franquicias estelares (Ej: LAD, NYY, HOU, PHI, TOR)
                        power_teams = ["LAD", "NYY", "HOU", "PHI", "TOR", "BAL", "ATL"]
                        bonus_away = 0.3 if away_team in power_teams else 0.0
                        bonus_home = 0.3 if home_team in power_teams else 0.0
                        
                        poder_v_total = v['sbr'] + bonus_away
                        poder_l_total = l['sbr'] + bonus_home
                        diff_poder = poder_v_total - poder_l_total
                        
                        if diff_poder > 0.5:
                            prob_v = min(round(50 + diff_poder * 12, 1), 88.0)
                            if st.button(f"Gana {away_team} ({prob_v}%)", key="ml_v", use_container_width=True): 
                                agregar_al_parlay(datos_juego['texto'], "Moneyline", f"Gana {away_team}", prob_v)
                        elif diff_poder < -0.5:
                            prob_l = min(round(50 + abs(diff_poder) * 12, 1), 88.0)
                            if st.button(f"Gana {home_team} ({prob_l}%)", key="ml_l", use_container_width=True): 
                                agregar_al_parlay(datos_juego['texto'], "Moneyline", f"Gana {home_team}", prob_l)
                        else:
                            st.caption("⚠️ Empate técnico (Evitar ML)")

                    with st.container(border=True):
                        st.markdown("**🎯 Ponches (K's)**")
                        proj_v = round((v['k9'] / 9) * 5.5, 1)
                        proj_l = round((l['k9'] / 9) * 5.5, 1)
                        
                        prob_kv = min(round(50 + max(0, v['k9'] - 8.5) * 5, 1), 85.0)
                        prob_kl = min(round(50 + max(0, l['k9'] - 8.5) * 5, 1), 85.0)
                        
                        if st.button(f"{v['nombre'].split()[-1]} Over {int(proj_v)-0.5} K's ({prob_kv}%)", key="kv", use_container_width=True): 
                            agregar_al_parlay(datos_juego['texto'], "Ponches", f"{v['nombre']} Over {int(proj_v)-0.5}", prob_kv)
                        if st.button(f"{l['nombre'].split()[-1]} Over {int(proj_l)-0.5} K's ({prob_kl}%)", key="kl", use_container_width=True): 
                            agregar_al_parlay(datos_juego['texto'], "Ponches", f"{l['nombre']} Over {int(proj_l)-0.5}", prob_kl)

                with col_m2:
                    with st.container(border=True):
                        st.markdown("**🔥 1ra Entrada**")
                        riesgo_quirurgico = v['fip'] + l['fip'] + (v['bb9']*1.2) + (l['bb9']*1.2)
                        
                        if riesgo_quirurgico < 9.5:
                            prob_nrfi = min(round(50 + (9.5 - riesgo_quirurgico) * 6, 1), 87.0)
                            if st.button(f"Añadir NRFI ({prob_nrfi}%)", key="nrfi", use_container_width=True): 
                                agregar_al_parlay(datos_juego['texto'], "1ra Entrada", "NRFI", prob_nrfi)
                        else:
                            prob_yrfi = min(round(50 + (riesgo_quirurgico - 9.5) * 6, 1), 87.0)
                            if st.button(f"Añadir YRFI ({prob_yrfi}%)", key="yrfi", use_container_width=True): 
                                agregar_al_parlay(datos_juego['texto'], "1ra Entrada", "YRFI", prob_yrfi)

                    with st.container(border=True):
                        st.markdown("**📈 Carreras Totales**")
                        total_quirurgico = (v['fip'] + l['fip']) * 1.15
                        st.caption(f"Proyectadas: {total_quirurgico:.1f}")
                        
                        if total_quirurgico > 9.0:
                            prob_over = min(round(50 + (total_quirurgico - 9.0) * 6, 1), 82.0)
                            if st.button(f"Over 8.5 Carreras ({prob_over}%)", key="over", use_container_width=True): 
                                agregar_al_parlay(datos_juego['texto'], "Totales", "Over 8.5", prob_over)
                        else:
                            prob_under = min(round(50 + (9.0 - total_quirurgico) * 6, 1), 82.0)
                            if st.button(f"Under 8.5 Carreras ({prob_under}%)", key="under", use_container_width=True): 
                                agregar_al_parlay(datos_juego['texto'], "Totales", "Under 8.5", prob_under)

# ==========================================
# PESTAÑA 2: AI SMART PICKS (ESCÁNER HÍBRIDO)
# ==========================================
with tab_ia_picks:
    st.markdown("### 🤖 Escáner Híbrido de la Jornada")
    st.markdown("La IA evalúa tanto el **pitcheo abridor** como el **factor de poder ofensivo del equipo** para recomendar ganadores con mayor respaldo.")
    
    if st.button("⚡ Ejecutar Escáner Híbrido", type="primary"):
        if not juegos_hoy:
            st.warning("No hay juegos hoy.")
        else:
            picks_ia_encontrados = []
            barra_progreso = st.progress(0)
            status_texto = st.empty()
            total_juegos = len(juegos_hoy)
            
            power_teams = ["LAD", "NYY", "HOU", "PHI", "TOR", "BAL", "ATL"]
            
            for i, juego in enumerate(juegos_hoy):
                status_texto.text(f"Analizando {juego['away']} @ {juego['home']}...")
                
                id_v = juego.get("v_id", "")
                id_l = juego.get("l_id", "")
                nombre_v = obtener_nombre_pitcher(id_v)
                nombre_l = obtener_nombre_pitcher(id_l)
                
                if nombre_v != "TBA" and nombre_l != "TBA":
                    stats_v, _ = obtener_estadisticas_avanzadas(nombre_v)
                    stats_l, _ = obtener_estadisticas_avanzadas(nombre_l)
                    
                    if stats_v and stats_l:
                        bonus_v = 0.3 if juego['away'] in power_teams else 0.0
                        bonus_l = 0.3 if juego['home'] in power_teams else 0.0
                        
                        poder_v_total = stats_v['sbr'] + bonus_v
                        poder_l_total = stats_l['sbr'] + bonus_l
                        diff = poder_v_total - poder_l_total
                        
                        if abs(diff) > 0.6:
                            fav_team = juego['away'] if diff > 0 else juego['home']
                            prob = min(round(60 + abs(diff) * 12, 1), 88.0)
                            picks_ia_encontrados.append({
                                "partido": juego["texto"],
                                "mercado": "Moneyline",
                                "seleccion": f"Gana {fav_team}",
                                "probabilidad": prob,
                                "razon": f"Modelo Híbrido: Ventaja de pitcheo combinada con fortaleza ofensiva del equipo."
                            })

                        if stats_v['ip'] > 30 and stats_v['k9'] >= 9.5:
                            proj_v = round((stats_v['k9'] / 9) * 5.5, 1)
                            line_v = int(proj_v) - 0.5
                            prob_kv = min(round(65 + (stats_v['k9'] - 9.5) * 4, 1), 88.0)
                            picks_ia_encontrados.append({
                                "partido": juego["texto"],
                                "mercado": "Ponches",
                                "seleccion": f"{nombre_v.split()[-1]} Over {line_v}",
                                "probabilidad": prob_kv,
                                "razon": f"Dominio de ponches sostenido (K/9: {stats_v['k9']})."
                            })

                        if stats_l['ip'] > 30 and stats_l['k9'] >= 9.5:
                            proj_l = round((stats_l['k9'] / 9) * 5.5, 1)
                            line_l = int(proj_l) - 0.5
                            prob_kl = min(round(65 + (stats_l['k9'] - 9.5) * 4, 1), 88.0)
                            picks_ia_encontrados.append({
                                "partido": juego["texto"],
                                "mercado": "Ponches",
                                "seleccion": f"{nombre_l.split()[-1]} Over {line_l}",
                                "probabilidad": prob_kl,
                                "razon": f"Dominio de ponches sostenido (K/9: {stats_l['k9']})."
                            })

                barra_progreso.progress((i + 1) / total_juegos)
            
            status_texto.text("¡Escaneo completado!")
            time.sleep(1)
            status_texto.empty()
            barra_progreso.empty()
            
            picks_ia_encontrados.sort(key=lambda x: x.get("probabilidad", 50.0), reverse=True)
            st.session_state.picks_ia = picks_ia_encontrados

    if 'picks_ia' in st.session_state and st.session_state.picks_ia:
        st.success(f"¡Se filtraron **{len(st.session_state.picks_ia)} selecciones** con el nuevo motor híbrido!")
        
        for idx, pick in enumerate(st.session_state.picks_ia):
            with st.container(border=True):
                col_p1, col_p2, col_p3 = st.columns([3, 1.5, 1])
                with col_p1:
                    st.markdown(f"⚾ **{pick.get('partido', '')}**")
                    st.markdown(f"🎯 **{pick.get('mercado', '')}:** `{pick.get('seleccion', '')}`")
                    st.caption(f"💡 *IA:* {pick.get('razon', '')}")
                with col_p2:
                    st.metric(label="Confianza IA", value=f"{pick.get('probabilidad', 75.0)}%")
                with col_p3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Añadir", key=f"ai_btn_{idx}", use_container_width=True):
                        agregar_al_parlay(pick.get('partido', ''), pick.get('mercado', ''), pick.get('seleccion', ''), pick.get('probabilidad', 75.0))

# --- 5. BARRA LATERAL: BOLETO DE PARLAY ---
with st.sidebar:
    st.markdown("### 🎫 MI ENTRADA")
    
    if len(st.session_state.parlay) == 0:
        st.caption("Aún no tienes selecciones en tu boleto.")
    else:
        prob_combinada_decimal = 1.0
        for pick in st.session_state.parlay:
            prob = float(pick['probabilidad']) / 100.0
            prob_combinada_decimal *= prob
            
        prob_porcentaje = prob_combinada_decimal * 100
        dec_odds = 1 / prob_combinada_decimal if prob_combinada_decimal > 0 else 1.0
        multiplicador_justo = f"{dec_odds:.2f}x"
            
        c_p, c_m = st.columns(2)
        with c_p:
            st.markdown(f"**Probabilidad**\n\n`{prob_porcentaje:.1f}%`")
        with c_m:
            st.markdown(f"**Momio Justo**\n\n`{multiplicador_justo}`")
            
        st.caption("💡 *Si Draftea te ofrece un multiplicador mayor a este, tienes valor (+EV).*")
        
        st.divider()
        
        parlay_por_partido = defaultdict(list)
        for pick in st.session_state.parlay:
            parlay_por_partido[pick['partido']].append(pick)
            
        for partido, picks in parlay_por_partido.items():
            with st.container(border=True):
                st.markdown(f"⚾ **{partido}**")
                for p in picks:
                    col_t, col_b = st.columns([75, 25])
                    with col_t:
                        st.markdown(f"• **{p['mercado']}:**\n{p['seleccion']} ({p['probabilidad']}%)")
                    with col_b:
                        st.button("X", key=f"del_{p['id']}", on_click=eliminar_del_parlay, args=(p['id'],), use_container_width=True)
        
        st.divider()
        c_btn1, c_btn2 = st.columns([6, 4])
        with c_btn1:
            st.success(f"**Total Picks:** {len(st.session_state.parlay)}")
        with c_btn2:
            if st.button("🗑️ Limpiar", type="secondary", use_container_width=True):
                limpiar_parlay()
