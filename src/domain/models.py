"""
Modelos de dominio con type hints completos.
Dataclasses inmutables (frozen=True) para garantizar integridad de datos.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List

from src.domain.enums import BetType, MatchPhase, PredictionConfidence, EVStatus


@dataclass(frozen=True)
class Team:
    """Equipo participante con validación de datos."""
    name: str
    fifa_ranking: int
    elo_rating: float
    
    def __post_init__(self):
        """Validar rango de rankings."""
        if self.fifa_ranking < 1 or self.fifa_ranking > 200:
            raise ValueError(f"Ranking inválido: {self.fifa_ranking}")
        if self.elo_rating < 0 or self.elo_rating > 3000:
            raise ValueError(f"Elo inválido: {self.elo_rating}")


@dataclass(frozen=True)
class Match:
    """Información de un partido con contexto estadístico."""
    match_id: str
    home_team: Team
    away_team: Team
    match_date: datetime
    phase: MatchPhase
    home_possession: Optional[float] = None
    home_shots: Optional[int] = None
    away_shots: Optional[int] = None
    previous_result: Optional[int] = None  # -1: Loss, 0: Draw, 1: Win
    
    def __post_init__(self):
        """Validar porcentaje de posesión."""
        if self.home_possession is not None:
            if not 0 <= self.home_possession <= 100:
                raise ValueError(f"Posesión inválida: {self.home_possession}")


@dataclass(frozen=True)
class OddsPair:
    """Par de cuota con mercado y timestamp."""
    bet_type: BetType
    odds_value: float
    bookmaker: str
    updated_at: datetime
    
    def __post_init__(self):
        """Validar rango de cuota."""
        if self.odds_value < 1.0 or self.odds_value > 1000.0:
            raise ValueError(f"Cuota fuera de rango: {self.odds_value}")


@dataclass(frozen=True)
class Prediction:
    """Predicción generada por modelo ML con metadata."""
    match_id: str
    bet_type: BetType
    predicted_probability: float  # 0.0 a 1.0
    confidence: PredictionConfidence
    model_version: str
    features_used: Dict[str, float] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validar probabilidad."""
        if not 0 <= self.predicted_probability <= 1.0:
            raise ValueError(
                f"Probabilidad fuera de rango [0,1]: {self.predicted_probability}"
            )


@dataclass(frozen=True)
class EVAnalysis:
    """Análisis completo de Valor Esperado (+EV)."""
    match_id: str
    bet_type: BetType
    market_odds: float
    implied_probability: float  # 1/odds
    predicted_probability: float
    ev_percent: float  # +EV como decimal (0.05 = +5%)
    status: EVStatus
    recommendation: str
    confidence: float  # 0.0 a 1.0
    analyzed_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validar cuota e probabilidades."""
        if self.market_odds < 1.0:
            raise ValueError(f"Cuota inválida: {self.market_odds}")
        if not 0 <= self.implied_probability <= 1.0:
            raise ValueError(
                f"Probabilidad implícita fuera de rango: {self.implied_probability}"
            )


@dataclass(frozen=True)
class BettingOpportunity:
    """Oportunidad de apuesta identificada y lista para actuar."""
    opportunity_id: str
    match: Match
    odds_pair: OddsPair
    prediction: Prediction
    ev_analysis: EVAnalysis
    alert_sent: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def is_positive_ev(self) -> bool:
        """Determinar si tiene +EV positivo."""
        return self.ev_analysis.status == EVStatus.POSITIVE
    
    @property
    def edge_percent(self) -> float:
        """Ventaja porcentual sobre cuota justa (0-100)."""
        return self.ev_analysis.ev_percent * 100


@dataclass
class AnalysisReport:
    """Reporte completo de un ciclo de análisis."""
    cycle_id: str
    timestamp: datetime
    matches_analyzed: int
    opportunities_found: List[BettingOpportunity]
    errors: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Porcentaje de análisis exitosos (0-100)."""
        if self.matches_analyzed == 0:
            return 0.0
        successful = self.matches_analyzed - len(self.errors)
        return (successful / self.matches_analyzed) * 100
    
    @property
    def high_confidence_opportunities(self) -> List[BettingOpportunity]:
        """Oportunidades con confianza > 75%."""
        return [
            opp for opp in self.opportunities_found
            if opp.ev_analysis.confidence > 0.75
        ]
