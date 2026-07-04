import os
import requests
import json

# Cargar variables de entorno seguras desde GitHub Secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def obtener_cuotas():
    # Buscamos cuotas de fútbol en las principales ligas (Ej: Premier League inglesa)
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('events', [])
    return []

def obtener_estadisticas_equipo(nombre_equipo):
    # Nota: En producción real mapearías IDs exactos. 
    # Esta función simula la llamada simplificada a API-Football para la demo funcional
    headers = {'x-rapidapi-key': API_FOOTBALL_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
    url = f"https://v3.football.api-sports.io/teams?search={nombre_equipo}"
    try:
        res = requests.get(url, headers=headers).json()
        if res.get("response"):
            team_id = res["response"][0]["team"]["id"]
            # Consultamos últimos partidos o rendimiento general
            url_stats = f"https://v3.football.api-sports.io/teams/statistics?team={team_id}&league=39&season=2024"
            stats = requests.get(url_stats, headers=headers).json()
            return stats.get("response", {})
    except Exception:
        return {"info": "No se pudieron precargar datos estadísticos avanzados."}
    return {}

def consultar_ia_rentabilidad(partido, cuotas, stats_local, stats_visita):
    # Prompt de ingeniería de apuestas para evitar "humo" y forzar análisis de valor (+EV)
    prompt = f"""
    Actúa como un analista cuantitativo de apuestas deportivas experto en Value Betting.
    Analiza el siguiente partido: {partido['home_team']} vs {partido['away_team']}.
    Cuotas del mercado actuales: {json.dumps(cuotas)}
    Estadísticas básicas cargadas: Local -> {json.dumps(stats_local)} | Visitante -> {json.dumps(stats_visita)}

    Instrucciones estrictas:
    1. Calcula implícitamente la probabilidad de cada resultado según las cuotas.
    2. Compara con el rendimiento histórico que deduzcas de los equipos.
    3. Determina si alguna cuota ofrece un Valor Esperado Positivo real (+EV).
    4. Si NO hay valor, responde estrictamente con la palabra: 'OMITIR'.
    5. Si SÍ hay valor, redacta una alerta de apuesta breve indicando: Selección, Cuota, Casa de apuesta y Argumento matemático rápido.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload)
        response_json = response.json()
        texto_ia = response_json['candidates'][0]['content']['parts'][0]['text']
        return texto_ia.strip()
    except Exception as e:
        return "OMITIR"

def ejecutar_bot():
    print("Iniciando escaneo del mercado...")
    partidos = obtener_cuotas()
    
    if not partidos:
        print("No se obtuvieron cuotas.")
        return
        
    # Analizamos los primeros 3 partidos de la lista para cuidar los créditos de las APIs gratis
    for partido in partidos[:3]:
        home = partido['home_team']
        away = partido['away_team']
        
        print(f"Analizando: {home} vs {away}")
        
        # Obtener métricas desde API-Football
        stats_local = obtener_estadisticas_equipo(home)
        stats_visita = obtener_estadisticas_equipo(away)
        
        bookmakers = partido.get('bookmakers', [])
        if not bookmakers:
            continue
            
        cuotas_filtradas = bookmakers[0]['markets'][0]['outcomes']
        
        # La IA procesa y dictamina el valor matemático
        veredicto = consultar_ia_rentabilidad(partido, cuotas_filtradas, stats_local, stats_visita)
        
        if "OMITIR" not in veredicto:
            alert_msg = f"🤖 *BOT ALERTA IA* 🤖\n\n{veredicto}"
            enviar_telegram(alert_msg)
            print("¡Apuesta con valor encontrada y notificada!")
        else:
            print("Partido analizado: Sin valor suficiente.")

if __name__ == "__main__":
    ejecutar_bot()
