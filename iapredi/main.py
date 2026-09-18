from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random

# Inicializamos la aplicación FastAPI
app = FastAPI(
    title="Motor Predictivo - AI Sports Analyst",
    description="API para procesar estadísticas y generar predicciones NRFI/YRFI",
    version="1.0.0"
)

# Configuración de CORS: Vital para que tu archivo index.html pueda hablar con este servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite peticiones desde cualquier lugar (cambiar en producción)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Definimos la estructura de datos que esperamos recibir del Frontend
class MatchupRequest(BaseModel):
    pitcher_visitante: str
    era_visitante: float
    pitcher_local: str
    era_local: float

# Este es el "Endpoint" (la ruta) al que llamará tu página web
@app.post("/predict_first_inning")
def generar_prediccion(matchup: MatchupRequest):
    
    # --- AQUÍ IRÍA TU MODELO DE MACHINE LEARNING REAL ---
    # Por ahora, usamos una lógica algorítmica básica para simular la IA
    
    # Calculamos un "índice de vulnerabilidad" basado en el ERA de ambos
    vulnerabilidad_combinada = matchup.era_visitante + matchup.era_local
    
    # Si la vulnerabilidad es baja, hay más chance de No Run (NRFI)
    if vulnerabilidad_combinada < 6.0:
        recomendacion = "NRFI (No Run First Inning)"
        # Asignamos una probabilidad base alta + un factor aleatorio simulando otras variables del modelo
        probabilidad = 65.0 + random.uniform(5.0, 20.0) 
        analisis = f"El modelo detecta solidez en la primera entrada. {matchup.pitcher_visitante} y {matchup.pitcher_local} combinan métricas de inicio dominante, sugiriendo bajo riesgo de anotación temprana."
    else:
        recomendacion = "YRFI (Yes Run First Inning)"
        probabilidad = 60.0 + random.uniform(5.0, 15.0)
        analisis = f"Alerta de riesgo temprana: El ERA combinado en primeras entradas sugiere vulnerabilidad al inicio del juego."

    # Devolvemos la respuesta formateada al frontend
    return {
        "status": "success",
        "recomendacion": recomendacion,
        "confianza": round(probabilidad, 1),
        "insight_texto": analisis
    }

# Ruta de prueba simple para verificar que el servidor está vivo
@app.get("/")
def home():
    return {"mensaje": "El Motor de IA está corriendo y listo para recibir datos."}