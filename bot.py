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
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error al enviar a Telegram: {e}")

def obtener_cuotas():
    # Identificador oficial en The Odds API para la Copa del Mundo de la FIFA
    url = f"https://the-odds-api.com{ODDS_API_KEY}&regions=eu&markets=h2h"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    print(f"Error en Odds API: {response.status_code} - {response.text}")
    return []

def obtener_estadisticas_seleccion(nombre_pais):
    headers = {'x-rapidapi-key': API_FOOTBALL_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
    # Buscamos el equipo nacional
    url = f"https://api-sports.io{nombre_pais}"
    try:
        res = requests.get(url, headers=headers).json()
        if res.get("response") and len(res["response"]) > 0:
            team_id = res["response"][0]["team"]["id"]
            # En API-Football, la Copa del Mundo es la League ID: 1. Temporada actual: 2026
            url_stats = f"https://api-sports.io{team_id}&league=1"
            stats = requests.get(url_stats, headers=headers).json()
            return stats.get("response", {})
    except Exception as e:
        print(f"Error buscando estadísticas para {nombre_pais}: {e}")
    return {"info": "No se pudieron precargar datos estadísticos del Mundial."}

def consultar_ia_rentabilidad(partido, cuotas, stats_local, stats_visita):
    prompt = f"""
    Actúa como un analista cuantitativo de apuestas deportivas experto en la Copa Mundial de la FIFA 2026.
    Analiza el siguiente partido de fase/eliminatoria mundialista: {partido['home_team']} vs {partido['away_team']}.
    Cuotas del mercado actuales (1X2): {json.dumps(cuotas)}
    Métricas de rendimiento en el torneo actual: Local -> {json.dumps(stats_local)} | Visitante -> {json.dumps(stats_visita)}

    Instrucciones estrictas:
    1. Calcula implícitamente la probabilidad de cada resultado según las cuotas que ofrecen las casas.
    2. Cruza la información con el rendimiento que traen las selecciones en este Mundial 2026.
    3. Determina si alguna cuota ofrece un Valor Esperado Positivo real (+EV).
    4. Si NO hay valor matemático claro, responde estrictamente con la palabra: 'OMITIR'.
    5. Si SÍ hay valor, redacta una alerta de apuesta breve indicando: Selección, Cuota, Casa de apuesta y tu análisis probabilístico libre de humo.
    """
    
    url = f"https://googleapis.com{GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload)
        response_json = response.json()
        texto_ia = response_json['candidates'][0]['content']['parts'][0]['text']
        return texto_ia.strip()
    except Exception as e:
        print(f"Error con Gemini IA: {e}")
        return "OMITIR"

def ejecutar_bot():
    print("Iniciando escaneo del mercado del Mundial 2026...")
    partidos = obtener_cuotas()
    
    if not partidos:
        print("No se obtuvieron cuotas o no hay partidos disponibles en este momento.")
        return
        
    # Analizamos los partidos disponibles del Mundial
    for partido in partidos[:4]:
        home = partido['home_team']
        away = partido['away_team']
        
        print(f"Analizando partido mundialista: {home} vs {away}")
        
        stats_local = obtener_estadisticas_seleccion(home)
        stats_visita = obtener_estadisticas_seleccion(away)
        
        bookmakers = partido.get('bookmakers', [])
        if not bookmakers:
            continue
            
        primer_bookmaker = bookmakers[0]
        casa_nombre = primer_bookmaker['title']
        cuotas_filtradas = primer_bookmaker['markets'][0]['outcomes']
        
        veredicto = consultar_ia_rentabilidad(partido, cuotas_filtradas, stats_local, stats_visita)
        
        if "OMITIR" not in veredicto:
            alert_msg = f"🏆 *MUNDIAL 2026 - ALERTA IA* 🏆\n*Casa:* {casa_nombre}\n\n{veredicto}"
            enviar_telegram(alert_msg)
            print("¡Apuesta mundialista con valor encontrada!")
        else:
            print("Partido analizado: Sin valor suficiente para invertir.")

if __name__ == "__main__":
    ejecutar_bot()
