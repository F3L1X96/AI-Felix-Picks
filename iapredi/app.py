import streamlit as st
import requests
import time
from datetime import datetime
from collections import defaultdict

st.set_page_config(page_title="AI Sports Analyst", page_icon="⚾", layout="wide")

if 'parlay' not in st.session_state:
    st.session_state.parlay = []

# --- 1. CONFIGURACIÓN DE API ---
API_KEY = "d0aa1d0b3amshb444051e088b6aep120b53jsndf0cdf41fcff" 
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com"
}

# --- 2. MOTORES DE EXTRACCIÓN OPTIMIZADOS ---

@st.cache_data(ttl=3600)
def obtener_juegos_hoy():
    if API_KEY == "" or API_KEY == "TU_API_KEY_AQUI":
        return [
            {"id": "1", "away": "CIN", "home": "MIL", "time": "6:40p", "epoch": 1, "texto": "6:40p — CIN @ MIL", "v_id": "", "l_id": ""},
            {"id": "2", "texto": "8:05p — TEX @ OAK", "away": "TEX", "home": "OAK", "time": "8:05p", "epoch": 2, "v_id": "", "l_id": ""}
        ]
        
    try:
        hoy = datetime.now().strftime('%Y%m%d')
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
            game_time = game_data.get("gameTime", "HOY")
            epoch_time = float(game_data.get("gameTime_epoch", 0))
            
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
                
        # ORDENAR CRONOLÓGICAMENTE POR HORA
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
        return None, f"Pitcher '{nombre}' no válido o no confirmado."
        
    try:
        url = "https://tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com/getMLBPlayerInfo"
        response = requests.get(url, headers=HEADERS, params={"playerName": nombre, "getStats": "true"}, timeout=10)
        datos = response.json()
        
        if datos.get("statusCode") != 200 or not datos.get("body"):
            return None, f"⚠️ No encontrado en Tank01: '{nombre}'."
            
        jugador_data = datos["body"][0]
        nombre_real = jugador_data.get("longName", nombre)
        stats_root = jugador_data.get("stats", {})
        
        s = stats_root["Pitching"] if "Pitching" in stats_root else stats_root
            
        era = float(s.get("ERA", "4.00"))
        whip = float(s.get("WHIP", "1.30"))
        ip = float(str(s.get("InningsPitched", "100")).replace('.1', '.33').replace('.2', '.66'))
        so = float(s.get("SO", s.get("strikeouts", "80")))
        hr = float(s.get("HR", "10"))
        bb = float(s.get("BB", "30"))
        
        k9 = round((so / ip) * 9, 2) if ip > 0 else 0
        bb9 = round((bb / ip) * 9, 2) if ip > 0 else 0
        fip = round(((13 * hr + 3 * bb - 2 * so) / ip) + 3.10, 2) if ip > 0 else 4.00
        
        return {
            "nombre": nombre_real, 
            "era": era, 
            "whip": whip, 
            "k9": k9, 
            "bb9": bb9,
            "fip": fip, 
            "ip": ip
        }, None
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

# --- 3. FUNCIONES DEL BOLETO ---
def agregar_al_parlay(partido, mercado, seleccion, cuota):
    st.session_state.parlay.append({
        "partido": partido,
        "mercado": mercado,
        "seleccion": seleccion,
        "cuota": cuota
    })
    st.rerun()

def limpiar_parlay():
    st.session_state.parlay = []
    st.rerun()

# --- 4. INTERFAZ PRINCIPAL ESTILO SOFASCORE ---
st.title("⚾ AI Felix Picks Analyst — Dashboard Quirúrgico")

col_lista, col_detalle = st.columns([3, 7])

with col_lista:
    st.markdown("### ⚡ Partidos de Hoy")
    juegos_hoy = obtener_juegos_hoy()
    
    if juegos_hoy:
        opciones_juegos = {j["texto"]: j for j in juegos_hoy}
        juego_seleccionado = st.radio("Selecciona un encuentro:", options=list(opciones_juegos.keys()), label_visibility="collapsed")
        datos_juego = opciones_juegos[juego_seleccionado]
    else:
        st.warning("No hay juegos hoy.")
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
        
        # CABECERA SOFASCORE CON LOGOS MÁS PEQUEÑOS Y COMPACTOS
        with st.container(border=True):
            col_lg1, col_info, col_lg2 = st.columns([2, 3, 2])
            with col_lg1:
                st.image(logo_away, width=35) # Tamaño reducido
                st.markdown(f"<div style='text-align: left;'><b>{away_team}</b> <span style='font-size: 11px; color: gray;'>Visita</span></div>", unsafe_allow_html=True)
            with col_info:
                st.markdown(f"<div style='text-align: center;'><h4 style='color: #1ed760; margin: 0;'>VS</h4><p style='margin: 0; font-size: 13px;'>🕒 {game_time}</p></div>", unsafe_allow_html=True)
            with col_lg2:
                st.image(logo_home, width=35) # Tamaño reducido
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
                with st.spinner("Calculando sabermetría..."):
                    datos_v, err_v = obtener_estadisticas_avanzadas(busqueda_v)
                    datos_l, err_l = obtener_estadisticas_avanzadas(busqueda_l)
                    
                    if err_v: st.error(err_v)
                    if err_l: st.error(err_l)
                    
                    if datos_v and datos_l:
                        st.session_state.v = datos_v
                        st.session_state.l = datos_l

        # Cuadrícula compacta de mercados si ya se procesó
        if 'v' in st.session_state:
            v = st.session_state.v
            l = st.session_state.l
            
            m1, m2, m3 = st.columns(3)
            with m1: st.caption(f"**FIP:** {v['nombre'].split()[-1]} `{v['fip']}` | {l['nombre'].split()[-1]} `{l['fip']}`")
            with m2: st.caption(f"**K/9:** {v['k9']} vs {l['k9']}")
            with m3: st.caption(f"**BB/9:** {v['bb9']} vs {l['bb9']}")
            
            st.divider()

            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                with st.container(border=True):
                    st.markdown("**🏆 Ganador (ML)**")
                    poder_v = v['k9'] - (v['fip'] + (v['bb9']*1.5))
                    poder_l = l['k9'] - (l['fip'] + (l['bb9']*1.5))
                    
                    if poder_v > poder_l + 1.0:
                        if st.button(f"Gana {away_team} (-115)", key="ml_v", use_container_width=True): 
                            agregar_al_parlay(datos_juego['texto'], "Moneyline", f"Gana {away_team}", "-115")
                    elif poder_l > poder_v + 1.0:
                        if st.button(f"Gana {home_team} (-120)", key="ml_l", use_container_width=True): 
                            agregar_al_parlay(datos_juego['texto'], "Moneyline", f"Gana {home_team}", "-120")
                    else:
                        st.caption("⚠️ Empate técnico")

                with st.container(border=True):
                    st.markdown("**🎯 Ponches (K's)**")
                    proj_v = round((v['k9'] / 9) * 6, 1)
                    proj_l = round((l['k9'] / 9) * 6, 1)
                    
                    if st.button(f"{v['nombre'].split()[-1]} Over {int(proj_v)-0.5} (-115)", key="kv", use_container_width=True): 
                        agregar_al_parlay(datos_juego['texto'], "Ponches", f"{v['nombre']} Over {int(proj_v)-0.5}", "-115")
                    if st.button(f"{l['nombre'].split()[-1]} Over {int(proj_l)-0.5} (-115)", key="kl", use_container_width=True): 
                        agregar_al_parlay(datos_juego['texto'], "Ponches", f"{l['nombre']} Over {int(proj_l)-0.5}", "-115")

            with col_m2:
                with st.container(border=True):
                    st.markdown("**🔥 1ra Entrada**")
                    riesgo_quirurgico = v['fip'] + l['fip'] + (v['bb9']*1.2) + (l['bb9']*1.2)
                    if riesgo_quirurgico < 10.5:
                        if st.button("Añadir NRFI (-130)", key="nrfi", use_container_width=True): 
                            agregar_al_parlay(datos_juego['texto'], "1ra Entrada", "NRFI", "-130")
                    else:
                        if st.button("Añadir YRFI (-110)", key="yrfi", use_container_width=True): 
                            agregar_al_parlay(datos_juego['texto'], "1ra Entrada", "YRFI", "-110")

                with st.container(border=True):
                    st.markdown("**📈 Carreras Totales**")
                    total_quirurgico = (v['fip'] + l['fip']) * 1.10
                    st.caption(f"Proyectadas: {total_quirurgico:.1f}")
                    
                    if total_quirurgico > 8.5:
                        if st.button("Over 8.5 Carreras (-110)", key="over", use_container_width=True): 
                            agregar_al_parlay(datos_juego['texto'], "Totales", "Over 8.5", "-110")
                    else:
                        if st.button("Under 8.5 Carreras (-110)", key="under", use_container_width=True): 
                            agregar_al_parlay(datos_juego['texto'], "Totales", "Under 8.5", "-110")

# --- 5. BARRA LATERAL: BOLETO DE PARLAY ---
with st.sidebar:
    st.markdown("### 🎫 MI ENTRADA")
    
    if len(st.session_state.parlay) == 0:
        st.caption("No hay selecciones en tu boleto. Explora los partidos y genera tus picks.")
    else:
        cuota_decimal_total = 1.0
        for pick in st.session_state.parlay:
            cuota_num = int(pick['cuota'].replace('+', ''))
            dec = (cuota_num / 100) + 1 if cuota_num > 0 else (100 / abs(cuota_num)) + 1
            cuota_decimal_total *= dec
        
        momio_final = f"+{int((cuota_decimal_total - 1) * 100)}" if cuota_decimal_total >= 2.0 else f"{int(-100 / (cuota_decimal_total - 1))}"
            
        c_in, c_mo, c_ga = st.columns(3)
        with c_in:
            apuesta = st.number_input("Entrada ($):", value=20, step=10)
        with c_mo:
            st.markdown(f"**Momio**\n\n`{momio_final}`")
        with c_ga:
            pago_potencial = apuesta * cuota_decimal_total
            st.markdown(f"**Ganancia**\n\n`$ {pago_potencial:.2f}`")
        
        st.divider()
        
        parlay_por_partido = defaultdict(list)
        for pick in st.session_state.parlay:
            parlay_por_partido[pick['partido']].append(pick)
            
        for partido, picks in parlay_por_partido.items():
            with st.container(border=True):
                st.markdown(f"⚾ **{partido}**")
                for p in picks:
                    st.markdown(f"• **{p['mercado']}:** {p['seleccion']} (`{p['cuota']}`)")
        
        st.divider()
        st.success(f"**Total Selecciones:** {len(st.session_state.parlay)}")
        
        if st.button("🗑️ Limpiar Boleto", type="secondary", use_container_width=True):
            limpiar_parlay()