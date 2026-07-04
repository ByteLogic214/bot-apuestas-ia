import os
import datetime
from typing import Optional, Dict


def get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta la variable de entorno requerida: {name}")
    return value


def calcular_ev(probabilidad: float, cuota: float) -> float:
    return (probabilidad * cuota) - 1


def calcular_cuota_justa(probabilidad: float) -> Optional[float]:
    if probabilidad <= 0:
        return None
    return 1 / probabilidad


def auditoria_valor_ia(home: str, away: str, market_odds: float, prob_modelo: float) -> Dict:
    cuota_justa = calcular_cuota_justa(prob_modelo)
    if cuota_justa is None:
        return {
            "partido": f"{home} vs {away}",
            "error": "Probabilidad inválida"
        }

    ev = calcular_ev(prob_modelo, market_odds)
    ventaja_pct = ((market_odds / cuota_justa) - 1) * 100
    recomendado = ev > 0.05

    return {
        "partido": f"{home} vs {away}",
        "probabilidad_modelo": round(prob_modelo * 100, 2),
        "cuota_mercado": market_odds,
        "cuota_justa": round(cuota_justa, 2),
        "ev": round(ev * 100, 2),
        "ventaja_pct": round(ventaja_pct, 2),
        "recomendado": recomendado,
    }


def obtener_datos_demo():
    return {
        "home": "Barcelona",
        "away": "Sevilla",
        "market_odds": 2.80,
        "prob_modelo": 0.42,
    }


def tarea_analisis():
    ahora = datetime.datetime.now().isoformat()
    print(f"[{ahora}] Iniciando ciclo de auditoría cuantitativa...")

    odds_api_key = get_env("ODDS_API_KEY")
    football_api_key = get_env("API_FOOTBALL_KEY")

    print("Claves cargadas correctamente.")
    print(f"ODDS_API_KEY cargada: {'sí' if odds_api_key else 'no'}")
    print(f"API_FOOTBALL_KEY cargada: {'sí' if football_api_key else 'no'}")

    datos = obtener_datos_demo()
    resultado = auditoria_valor_ia(
        home=datos["home"],
        away=datos["away"],
        market_odds=datos["market_odds"],
        prob_modelo=datos["prob_modelo"],
    )

    print("Resultado del análisis:")
    for k, v in resultado.items():
        print(f"- {k}: {v}")

    if resultado.get("recomendado"):
        print("Pick con valor esperado positivo detectado.")
    else:
        print("No se detectó una apuesta con valor suficiente.")

    print("Ciclo completado.")


if __name__ == "__main__":
    try:
        tarea_analisis()
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
        raise
