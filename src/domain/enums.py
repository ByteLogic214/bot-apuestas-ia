"""
Enumeraciones tipadas para el dominio de apuestas.
Mejora type safety y evita strings hardcodeados.
"""

from enum import Enum
from typing import Literal


class BetType(str, Enum):
    """Tipos de apuestas soportadas."""
    WIN_HOME = "1"          # Local gana
    DRAW = "X"              # Empate
    WIN_AWAY = "2"          # Visitante gana
    UNDER_OVER = "OVER"     # Over/Under goles
    BOTH_SCORE = "BTTS"     # Ambos equipos anotan


class MatchPhase(str, Enum):
    """Fases de un partido en el mundial."""
    FRIENDLY = "Amistoso"
    GROUP_STAGE = "Mundial_Grupos"
    ROUND_16 = "Mundial_16avos"
    QUARTERFINALS = "Mundial_Cuartos"
    SEMIFINALS = "Mundial_Semis"
    THIRD_PLACE = "Tercer_Lugar"
    FINAL = "Final"


class PredictionConfidence(str, Enum):
    """Nivel de confianza en predicción."""
    VERY_LOW = "muy_baja"      # < 30%
    LOW = "baja"               # 30-50%
    MEDIUM = "media"           # 50-70%
    HIGH = "alta"              # 70-85%
    VERY_HIGH = "muy_alta"     # > 85%


class EVStatus(str, Enum):
    """Estado de análisis +EV."""
    POSITIVE = "positivo"      # +EV encontrado
    NEGATIVE = "negativo"      # Sin +EV
    SKIPPED = "omitido"        # Datos insuficientes
    ERROR = "error"            # Fallo en análisis


class BettingMarket(str, Enum):
    """Mercados de apuestas disponibles."""
    MONEYLINE = "h2h"          # 1X2
    SPREAD = "spreads"         # Handicap
    TOTALS = "totals"          # Over/Under
    ASIAN_HANDICAP = "asian_handicap"


class TimeFrame(str, Enum):
    """Marcos de tiempo para análisis."""
    REALTIME = "tiempo_real"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


# Type aliases para mayor claridad
BetOdds = float  # Cuota: 2.50, 1.80, etc
EVPercent = float  # Porcentaje +EV: 0.05 = +5%
Confidence = float  # 0.0 a 1.0
