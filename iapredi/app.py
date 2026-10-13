import streamlit as st
import requests
import time
import uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# 1. CONFIGURACIÓN INICIAL DE LA PÁGINA (Debe ir siempre al principio)
st.set_page_config(page_title="AI Felix Picks Analyst", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

# 2. INICIALIZACIÓN DE VARIABLES DE SESIÓN (Memoria de la app)
if 'parlay' not in st.session_state:
    st.session_state.parlay = []
if 'deporte_seleccionado' not in st.session_state:
    st.session_state.deporte_seleccionado = None

# --- CONFIGURACIÓN DE API (Tank01 - MLB) ---
API_KEY = "abe8de41edmsh6fc305a3060e567p1727f6jsn3ba0c025c6e9" # <- RECUERDA PONER TU LLAVE AQUÍ
HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com"
}

# Configuración de Zona Horaria (UTC-6)
tz_centro = timezone(timedelta(hours=-6))

# ==========================================
# FUNCIONES: MOTORES DE EXTRACCIÓN Y SABERMETRÍA (MLB)
# ==========================================

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

def evaluar_f5_quirurgico(sbr_v, whip_v, fip_v, era_v, sbr_l, whip_l, fip_l, era_l, equipo_v, equipo_l):
    if (fip_v < 3.50 and whip_v < 1.20) and (fip_l < 3.50 and whip_l < 1.20):
        return "🛡️ ALERTA: Duelo de Ases. Posible Empate 0-0 F5.", "Under F5", 70.0
        
    diff_poder = sbr_v - sbr_l
    
    if abs(diff_poder) > 0.7:
        prob_calculada = min(round(50 + abs(diff_poder) * 12, 1), 88.0)
        
        if diff_poder > 0:
            fav_equipo, fav_whip, fav_fip = equipo_v, whip_v, fip_v
            riv_era, riv_fip = era_l, fip_l
        else:
            fav_equipo, fav_whip, fav_fip = equipo_l, whip_l, fip_l
            riv_era, riv_fip = era_v, fip_v
            
        if prob_calculada >= 75.0:
            if fav_whip < 1.25:
                if riv_era > 4.50 or riv_fip > 4.50:
                    return f"🔥 F5 MONEYLINE: Dominio de {fav_equipo} y Rival Débil.", f"Gana {fav_equipo} (1-5 E)", prob_calculada
                else:
                    return f"⚠️ ABORTAR F5: El pitcher rival es decente. Riesgo de empate.", None, 0
            else:
                return f"⚠️ ABORTAR F5: Tu abridor ({fav_equipo}) permite muchos corredores (WHIP Alto).", None, 0
                
    return "❌ SIN VALOR EN F5: Juego cerrado o métricas insuficientes.", None, 0

def evaluar_primera_entrada(fip_v, era_v, fip_l, era_l):
    if fip_v < 3.20 and era_v < 3.50 and fip_l < 3.20 and era_l < 3.50:
        return "💎 NRFI (NO Anotan en 1ra): Ambos abridores son intocables.", "NRFI", 82.0
    elif (fip_v > 4.50 or era_v > 5.00) and (fip_l > 4.50 or era_l > 5.00):
        return "🎯 YRFI (SÍ Anotan en 1ra): Ambos abridores reciben castigo duro.", "YRFI", 78.0
    return "Paso", None, 0

def evaluar_ponches_draftea(k9, avg_ip, nombre):
    if k9 < 8.0 or avg_ip < 4.0:
        return "❌ Volumen insuficiente.", None, 0
        
    proyeccion = round((k9 / 9) * avg_ip, 1)
    linea_base_draftea = int(proyeccion) - 0.5 
    colchon = proyeccion - linea_base_draftea
    
    if colchon >= 1.2:
        prob = min(round(60 + (k9 - 8.0) * 4 + colchon * 5, 1), 88.0)
        return f"✅ VALOR EN OVER: Proyecta {proyeccion} K's (Colchón +{round(colchon,2)}).", f"{nombre.split()[-1]} Over {linea_base_draftea}", prob
    return f"❌ Línea ajustada. Margen de solo {round(colchon, 2)} K's.", None, 0

# --- FUNCIONES DEL BOLETO Y UI ---
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
