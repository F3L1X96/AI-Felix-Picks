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
API_KEY = "abe8de41edmsh6fc305a3060e567p1727f6jsn3ba0c025c6e9" # <- RECUERDA PONER TU LLAVE AQUÍ
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com"
}

# Configuración de Zona Horaria (UTC-6)
tz_centro = timezone(timedelta(hours=-6))

# --- 2. MOTORES DE EXTRACCIÓN Y SABERMETRÍA PULIDOS ---

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
        resp_p = requests.get(url_p, headers=HEADERS, params={"playerID": player_id}, timeout=5)
        if resp_p.status_code == 429: return "LIMITE_API"
        
        datos = resp_p.json()
        if datos.get("statusCode") == 200:
            body = datos.get("body")
            if isinstance(body, list) and len(body) > 0:
                return body[0].get("longName", "TBA")
            elif isinstance(body, dict):
                return body.get("longName", "TBA")
    except:
        pass
    return "TBA"

@st.cache_data(ttl=3600)
def obtener_estadisticas_avanzadas(nombre):
    if not nombre or nombre.strip() == "" or nombre == "TBA":
        return None, "TBA"
        
    try:
        url = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBPlayerInfo"
        params = {"playerName": nombre, "getStats": "true"}
            
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 429:
            return None, "LIMITE_API"
            
        datos = response.json()
        if datos.get("statusCode") == 429 or ("message" in datos and "exceeded" in datos["message"].lower()):
            return None, "LIMITE_API"
            
        if datos.get("statusCode") != 200 or not datos.get("body"):
            return None, f"⚠️ No encontrado."
            
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
        
        juegos = float(s.get("GamesStarted", s.get("GS", s.get("gamesStarted", s.get("G", 0)))) or 0)
        avg_ip = round(ip / juegos, 1) if juegos > 0 else 5.0
        if avg_ip > 7.0: avg_ip = 6.0 
        if avg_ip < 1.0: avg_ip = 4.0 
        
        k9 = round((so / ip) * 9, 2) if ip > 0 else 0.0
        bb9 = round((bb / ip) * 9, 2) if ip > 0 else 0.0
        fip = round(((13 * hr + 3 * bb - 2 * so) / ip) + 3.10, 2) if ip > 0 else 4.50
        
        confianza_ip = min(ip / 40.0, 1.0)
        fip_ajustado = fip * confianza_ip + 4.50 * (1 - confianza_ip)
        
        sbr_poder = ((k9 - 8.5) * 0.15) + ((3.2 - bb9) * 0.15) + ((4.10 - fip_ajustado) * 0.70)
        
        return {
            "nombre": nombre_real, 
            "era": era, 
            "whip": whip, 
            "k9": k9, 
            "bb9": bb9,
            "fip": fip_ajustado, 
            "ip": ip,
            "avg_ip": avg_ip,
            "sbr": sbr_poder
        }, None
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

# --- 3. NUEVOS MÓDULOS DE EVALUACIÓN V2.1 ---

def evaluar_f5_quirurgico(sbr_v, whip_v, fip_v, era_v, sbr_l, whip_l, fip_l, era_l, equipo_v, equipo_l):
    """Evalúa Primeras 5 Entradas con el triple candado de seguridad."""
    # 1. CANDADO ANTI-EMPATES (Duelo de Ases)
    if (fip_v < 3.50 and whip_v < 1.20) and (fip_l < 3.50 and whip_l < 1.20):
        return "🛡️ ALERTA: Duelo de Ases. Posible Empate 0-0 F5.", "Under F5", 70.0
        
    diff_poder = sbr_v - sbr_l
    
    # Determinar quién es el favorito real según la IA
    if abs(diff_poder) > 0.7:
        prob_calculada = min(round(50 + abs(diff_poder) * 12, 1), 88.0)
        
        if diff_poder > 0:
            fav_equipo, fav_whip, fav_fip = equipo_v, whip_v, fip_v
            riv_era, riv_fip = era_l, fip_l
        else:
            fav_equipo, fav_whip, fav_fip = equipo_l, whip_l, fip_l
            riv_era, riv_fip = era_v, fip_v
            
        # 2. CANDADO ANTI-COLAPSOS (El favorito no debe permitir tráfico en bases)
        if prob_calculada >= 75.0:
            if fav_whip < 1.25:
                # 3. CANDADO DE VÍCTIMA COMPROBADA (El rival debe ser débil)
                if riv_era > 4.50 or riv_fip > 4.50:
                    return f"🔥 F5 MONEYLINE: Dominio de {fav_equipo} y Rival Débil.", f"Gana {fav_equipo} (1-5 E)", prob_calculada
                else:
                    return f"⚠️ ABORTAR F5: El pitcher rival es decente. Riesgo de empate.", None, 0
            else:
                return f"⚠️ ABORTAR F5: Tu abridor ({fav_equipo}) permite muchos corredores (WHIP Alto).", None, 0
                
    return "❌ SIN VALOR EN F5: Juego cerrado o métricas insuficientes.", None, 0

def evaluar_primera_entrada(fip_v, era_v, fip_l, era_l):
    """Caza anomalías YRFI/NRFI cruzando ERA y FIP general como proxy."""
    if fip_v < 3.20 and era_v < 3.50 and fip_l < 3.20 and era_l < 3.50:
        return "💎 NRFI (NO Anotan en 1ra): Ambos abridores son intocables.", "NRFI", 82.0
    elif (fip_v > 4.50 or era_v > 5.00) and (fip_l > 4.50 or era_l > 5.00):
        return "🎯 YRFI (SÍ Anotan en 1ra): Ambos abridores reciben castigo duro.", "YRFI", 78.0
    return "Paso", None, 0

def evaluar_ponches_draftea(k9, avg_ip, nombre):
    """Calcula automáticamente el colchón matemático para los ponches."""
    if k9 < 8.0 or avg_ip < 4.0:
        return "❌ Volumen insuficiente.", None, 0
        
    proyeccion = round((k9 / 9) * avg_ip, 1)
    linea_base_draftea = int(proyeccion) - 0.5 
    colchon = proyeccion - linea_base_draftea
    
    if colchon >= 1.2:
        prob = min(round(60 + (k9 - 8.0) * 4 + colchon * 5, 1), 88.0)
        return f"✅ VALOR EN OVER: Proyecta {proyeccion} K's (Colchón +{round(colchon,2)}).", f"{nombre.split()[-1]} Over {linea_base_draftea}", prob
    return f"❌ Línea ajustada. Margen de solo {round(colchon, 2)} K's.", None, 0


# --- 4. FUNCIONES DEL BOLETO Y UI ---
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

def renderizar_boton_pick(texto_boton, partido, mercado, seleccion, probabilidad, key_id):
    existe = any(p['partido'] == partido and p['mercado'] == mercado and p['seleccion'] == seleccion for p in st.session_state.parlay)
    if existe:
        st.button("✅ Añadido", disabled=True, key=f"btn_dis_{key_id}", use_container_width=True)
    else:
        if st.button(texto_boton, key=f"btn_add_{key_id}", use_container_width=True):
            agregar_al_parlay(partido, mercado, seleccion, probabilidad)

# --- 5. INTERFAZ PRINCIPAL ---
st.title("⚾ AI Felix Picks Analyst — Motor Quirúrgico v2.1")

tab_analizador, tab_ia_picks = st.tabs(["🏟️ Analizador por Partido", "🤖 AI Smart Picks (Filtro Strict)"])

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
            
            if nombre_v_inicial == "LIMITE_API" or nombre_l_inicial == "LIMITE_API":
                st.error("🚨 Límite de API de RapidAPI agotado. Ingresa tu nueva Key.")
            
            away_team = datos_juego["away"]
            home_team = datos_juego["home"]
            game_time = datos_juego["time"]
            game_id = datos_juego['id']
            
            logo_away = f"https://a.espncdn.com/i/teamlogos/mlb/500/{away_team.lower()}.png"
            logo_home = f"https://a.espncdn.com/i/teamlogos/mlb/500/{home_team.lower()}.png"
            
            with st.container(border=True):
                col_lg1, col_info, col_lg2 = st.columns([2, 3, 2])
                with col_lg1:
                    st.image(logo_away, width=35)
                    st.markdown(f"<div style='text-align: left;'><b>{away_team}</b></div>", unsafe_allow_html=True)
                with col_info:
                    st.markdown(f"<div style='text-align: center;'><h4 style='color: #1ed760; margin: 0;'>VS</h4><p style='margin: 0; font-size: 13px;'>🕒 {game_time}</p></div>", unsafe_allow_html=True)
                with col_lg2:
                    st.image(logo_home, width=35)
                    st.markdown(f"<div style='text-align: right;'><b>{home_team}</b></div>", unsafe_allow_html=True)
                
                st.divider()
                
                c_inf1, c_inf2, c_btn = st.columns([4, 4, 3])
                with c_inf1: 
                    busqueda_v = st.text_input(f"Pitcher Visita", value=nombre_v_inicial if nombre_v_inicial != "LIMITE_API" else "", key=f"v_{datos_juego['id']}")
                with c_inf2: 
                    busqueda_l = st.text_input(f"Pitcher Local", value=nombre_l_inicial if nombre_l_inicial != "LIMITE_API" else "", key=f"l_{datos_juego['id']}")
                with c_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    generar = st.button("🚀 Analizar", type="primary", use_container_width=True)

                if generar:
                    with st.spinner("Calculando modelo sabermétrico estricto..."):
                        datos_v, err_v = obtener_estadisticas_avanzadas(busqueda_v)
                        datos_l, err_l = obtener_estadisticas_avanzadas(busqueda_l)
                        
                        if err_v == "LIMITE_API" or err_l == "LIMITE_API":
                            st.error("🚨 Límite de la API agotado. Actualiza tu API Key.")
                        else:
                            if err_v: st.error(err_v)
                            if err_l: st.error(err_l)
                            
                            if datos_v and datos_l:
                                st.session_state.v = datos_v
                                st.session_state.l = datos_l

            if 'v' in st.session_state and 'l' in st.session_state:
                v = st.session_state.v
                l = st.session_state.l
                
                m1, m2, m3, m4 = st.columns(4)
                with m1: st.caption(f"**IP/Start:** {v['avg_ip']} vs {l['avg_ip']}")
                with m2: st.caption(f"**FIP:** {v['fip']:.2f} vs {l['fip']:.2f}")
                with m3: st.caption(f"**K/9:** {v['k9']} vs {l['k9']}")
                with m4: st.caption(f"**BB/9:** {v['bb9']} vs {l['bb9']}")
                
                st.divider()

                col_m1, col_m2 = st.columns(2)
                
                # --- F5 MONEYLINE ---
                with col_m1:
                    with st.container(border=True):
                        st.markdown("**🏆 F5 (Primeras 5 Entradas)**")
                        razon_f5, seleccion_f5, prob_f5 = evaluar_f5_quirurgico(
                            v['sbr'], v['whip'], v['fip'], v['era'], 
                            l['sbr'], l['whip'], l['fip'], l['era'], 
                            away_team, home_team
                        )
                        st.caption(f"💡 {razon_f5}")
                        if seleccion_f5:
                            renderizar_boton_pick(f"{seleccion_f5} ({prob_f5}%)", datos_juego['texto'], "F5 Moneyline", seleccion_f5, prob_f5, f"f5_{game_id}")

                # --- PONCHES ---
                    with st.container(border=True):
                        st.markdown("**🎯 Ponches (K's)**")
                        razon_kv, sel_kv, prob_kv = evaluar_ponches_draftea(v['k9'], v['avg_ip'], v['nombre'])
                        razon_kl, sel_kl, prob_kl = evaluar_ponches_draftea(l['k9'], l['avg_ip'], l['nombre'])
                        
                        st.caption(f"VISITA: {razon_kv}")
                        if sel_kv:
                            renderizar_boton_pick(f"{sel_kv} K's ({prob_kv}%)", datos_juego['texto'], "Ponches", sel_kv, prob_kv, f"kv_{game_id}")
                            
                        st.caption(f"LOCAL: {razon_kl}")
                        if sel_kl:
                            renderizar_boton_pick(f"{sel_kl} K's ({prob_kl}%)", datos_juego['texto'], "Ponches", sel_kl, prob_kl, f"kl_{game_id}")

                # --- 1RA ENTRADA ---
                with col_m2:
                    with st.container(border=True):
                        st.markdown("**🔥 1ra Entrada (YRFI/NRFI)**")
                        razon_1ra, sel_1ra, prob_1ra = evaluar_primera_entrada(v['fip'], v['era'], l['fip'], l['era'])
                        
                        st.caption(f"💡 {razon_1ra}")
                        if sel_1ra:
                            renderizar_boton_pick(f"Añadir {sel_1ra} ({prob_1ra}%)", datos_juego['texto'], "1ra Entrada", sel_1ra, prob_1ra, f"1ra_{game_id}")

                # --- TOTALES ---
                    with st.container(border=True):
                        st.markdown("**📈 Carreras Totales**")
                        total_quirurgico = (v['fip'] + l['fip']) * 1.15
                        st.caption(f"Métrica proyectada: {total_quirurgico:.1f} (Peligro si > 9.5)")
                        
                        if total_quirurgico > 9.5:
                            prob_over = min(round(50 + (total_quirurgico - 9.5) * 6, 1), 82.0)
                            renderizar_boton_pick(f"Over 8.5 Carreras ({prob_over}%)", datos_juego['texto'], "Totales", "Over 8.5", prob_over, f"over_{game_id}")
                        elif total_quirurgico < 7.5:
                            prob_under = min(round(50 + (7.5 - total_quirurgico) * 6, 1), 82.0)
                            renderizar_boton_pick(f"Under 8.5 Carreras ({prob_under}%)", datos_juego['texto'], "Totales", "Under 8.5", prob_under, f"under_{game_id}")
                        else:
                            st.caption("Línea apretada. Mejor no jugar totales.")

# ==========================================
# PESTAÑA 2: AI SMART PICKS (ESCÁNER ESTRICTO)
# ==========================================
with tab_ia_picks:
    st.markdown("### 🤖 Escáner Quirúrgico de la Jornada (v2.1)")
    st.markdown("Nuevos candados activos: Protección Anti-Empates F5, Colchón Automático de K's y Cazador de 1ra Entrada.")
    
    if st.button("⚡ Ejecutar Escáner Seguro", type="primary"):
        if not juegos_hoy:
            st.warning("No hay juegos hoy.")
        else:
            picks_ia_encontrados = []
            barra_progreso = st.progress(0)
            status_texto = st.empty()
            total_juegos = len(juegos_hoy)
            api_limite_alcanzado = False
            
            for i, juego in enumerate(juegos_hoy):
                status_texto.text(f"Analizando {juego['away']} @ {juego['home']}...")
                
                id_v = juego.get("v_id", "")
                id_l = juego.get("l_id", "")
                
                if id_v and id_l:
                    nombre_v = obtener_nombre_pitcher(id_v)
                    nombre_l = obtener_nombre_pitcher(id_l)
                    
                    if nombre_v == "LIMITE_API" or nombre_l == "LIMITE_API":
                        api_limite_alcanzado = True
                        break
                        
                    if nombre_v != "TBA" and nombre_l != "TBA":
                        stats_v, err_v = obtener_estadisticas_avanzadas(nombre_v)
                        stats_l, err_l = obtener_estadisticas_avanzadas(nombre_l)
                        
                        if err_v == "LIMITE_API" or err_l == "LIMITE_API":
                            api_limite_alcanzado = True
                            break
                            
                        if stats_v and stats_l:
                            # ESCANEO F5 MONEYLINE V2.1
                            razon_f5, sel_f5, prob_f5 = evaluar_f5_quirurgico(
                                stats_v['sbr'], stats_v['whip'], stats_v['fip'], stats_v['era'],
                                stats_l['sbr'], stats_l['whip'], stats_l['fip'], stats_l['era'],
                                juego['away'], juego['home']
                            )
                            if sel_f5:
                                picks_ia_encontrados.append({
                                    "partido": juego["texto"],
                                    "mercado": "F5 Moneyline",
                                    "seleccion": sel_f5,
                                    "probabilidad": prob_f5,
                                    "razon": razon_f5
                                })

                            # ESCANEO PONCHES AUTOMÁTICO V2.1
                            for stats in [stats_v, stats_l]:
                                razon_k, sel_k, prob_k = evaluar_ponches_draftea(stats['k9'], stats['avg_ip'], stats['nombre'])
                                if sel_k:
                                    picks_ia_encontrados.append({
                                        "partido": juego["texto"],
                                        "mercado": "Ponches",
                                        "seleccion": sel_k,
                                        "probabilidad": prob_k,
                                        "razon": razon_k
                                    })

                            # ESCANEO 1RA ENTRADA V2.1
                            razon_1ra, sel_1ra, prob_1ra = evaluar_primera_entrada(stats_v['fip'], stats_v['era'], stats_l['fip'], stats_l['era'])
                            if sel_1ra:
                                picks_ia_encontrados.append({
                                    "partido": juego["texto"],
                                    "mercado": "1ra Entrada",
                                    "seleccion": sel_1ra,
                                    "probabilidad": prob_1ra,
                                    "razon": razon_1ra
                                })
                
                barra_progreso.progress((i + 1) / total_juegos)
            
            if api_limite_alcanzado:
                status_texto.empty()
                barra_progreso.empty()
                st.error("🚨 **LÍMITE DE API ALCANZADO:** Se te acabaron las consultas de tu API Key.")
            else:
                status_texto.text("¡Escaneo completado!")
                time.sleep(1)
                status_texto.empty()
                barra_progreso.empty()
                
                picks_ia_encontrados.sort(key=lambda x: x.get("probabilidad", 50.0), reverse=True)
                st.session_state.picks_ia = picks_ia_encontrados

    if 'picks_ia' in st.session_state and st.session_state.picks_ia:
        st.success(f"¡Filtro Quirúrgico detectó **{len(st.session_state.picks_ia)} selecciones** rentables!")
        
        for idx, pick in enumerate(st.session_state.picks_ia):
            with st.container(border=True):
                col_p1, col_p2, col_p3 = st.columns([3, 1.5, 1])
                with col_p1:
                    st.markdown(f"⚾ **{pick.get('partido', '')}**")
                    st.markdown(f"🎯 **{pick.get('mercado', '')}:** `{pick.get('seleccion', '')}`")
                    st.caption(f"💡 *IA:* {pick.get('razon', '')}")
                with col_p2:
                    st.metric(label="Confianza", value=f"{pick.get('probabilidad', 75.0)}%")
                with col_p3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    renderizar_boton_pick("Añadir", pick.get('partido', ''), pick.get('mercado', ''), pick.get('seleccion', ''), pick.get('probabilidad', 75.0), f"ai_btn_{idx}")
    elif 'picks_ia' in st.session_state and not st.session_state.picks_ia:
        st.info("La IA no encontró nada que supere los filtros matemáticos anti-riesgo. Guardar bankroll.")

# --- 6. BARRA LATERAL: BOLETO DE PARLAY ---
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
            
        st.caption("💡 *Asegúrate de que Draftea te ofrezca un momio similar o mejor.*")
        
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
