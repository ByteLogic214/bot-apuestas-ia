"""
Cálculo de Valor Esperado (+EV) con validación y análisis probabilístico.
Lógica central del sistema: identifica apuestas rentables.
"""

import logging
from typing import Optional
from datetime import datetime
import uuid

from src.core.config import get_config
from src.core.exceptions import EVCalculationException, ValidationException
from src.domain.models import (
    Match, OddsPair, Prediction, EVAnalysis, BettingOpportunity
)
from src.domain.enums import EVStatus

logger = logging.getLogger(__name__)


class EVCalculator:
    """
    Calcula Valor Esperado (+EV) de apuestas.
    Fórmula: EV = (P_real * cuota) - 1
    Donde P_real es probabilidad predicha y cuota es el decimal
    """
    
    def __init__(self):
        self.config = get_config()
        self.bot_config = self.config.get_bot_config()
    
    def calculate(self, odds_pair: OddsPair,
                  predicted_prob: float) -> EVAnalysis:
        """
        Calcular +EV para una cuota y probabilidad predicha.
        
        Args:
            odds_pair: Par de cuota (valor decimal)
            predicted_prob: Probabilidad predicha (0-1)
        
        Returns:
            EVAnalysis con resultado del cálculo
        
        Raises:
            ValidationException: Si los inputs son inválidos
        """
        # Validar inputs
        self._validate_inputs(odds_pair, predicted_prob)
        
        # Calcular probabilidad implícita
        implied_prob = 1 / odds_pair.odds_value
        
        # Calcular EV
        # EV = (P_real * cuota) - 1
        ev_value = (predicted_prob * odds_pair.odds_value) - 1
        
        # Convertir a porcentaje
        ev_percent = ev_value
        
        # Determinar status
        status = self._determine_status(ev_percent)
        
        # Generar recomendación
        recommendation = self._generate_recommendation(
            status=status,
            ev_percent=ev_percent,
            predicted_prob=predicted_prob,
            implied_prob=implied_prob
        )
        
        # Calcular confianza basada en diferencia de probabilidades
        confidence = self._calculate_confidence(
            predicted_prob, implied_prob, status
        )
        
        analysis = EVAnalysis(
            match_id="",  # Se establece en BettingOpportunity
            bet_type=odds_pair.bet_type,
            market_odds=odds_pair.odds_value,
            implied_probability=implied_prob,
            predicted_probability=predicted_prob,
            ev_percent=ev_percent,
            status=status,
            recommendation=recommendation,
            confidence=confidence
        )
        
        logger.debug(
            f"EV calculado: {odds_pair.bet_type.value} @ {odds_pair.odds_value} = "
            f"+{ev_percent*100:.1f}% ({status.value})"
        )
        
        return analysis
    
    def _validate_inputs(self, odds_pair: OddsPair,
                        predicted_prob: float) -> None:
        """
        Validar que los inputs sean válidos.
        
        Args:
            odds_pair: Cuota
            predicted_prob: Probabilidad predicha
        
        Raises:
            ValidationException: Si hay error de validación
        """
        if odds_pair.odds_value < 1.0 or odds_pair.odds_value > 1000.0:
            raise ValidationException(
                f"Cuota fuera de rango [1.0, 1000.0]: {odds_pair.odds_value}"
            )
        
        if not 0 <= predicted_prob <= 1.0:
            raise ValidationException(
                f"Probabilidad predicha debe estar en [0,1]: {predicted_prob}"
            )
        
        if predicted_prob == 0 or predicted_prob == 1:
            logger.warning(
                f"Probabilidad extrema: {predicted_prob}. "
                f"Puede indicar predicción poco confiable."
            )
    
    def _determine_status(self, ev_percent: float) -> EVStatus:
        """
        Determinar si hay +EV positivo.
        
        Args:
            ev_percent: Porcentaje de EV
        
        Returns:
            EVStatus (POSITIVE, NEGATIVE, SKIPPED, ERROR)
        """
        if ev_percent < 0:
            return EVStatus.NEGATIVE
        
        if ev_percent < self.bot_config.min_ev_threshold:
            return EVStatus.SKIPPED  # EV positivo pero por debajo del umbral
        
        if ev_percent > self.bot_config.max_ev_threshold:
            return EVStatus.POSITIVE  # +EV extraordinario
        
        return EVStatus.POSITIVE
    
    def _generate_recommendation(self, status: EVStatus, ev_percent: float,
                                 predicted_prob: float,
                                 implied_prob: float) -> str:
        """
        Generar recomendación textual basada en análisis.
        
        Args:
            status: Status del análisis
            ev_percent: Porcentaje EV
            predicted_prob: Probabilidad predicha
            implied_prob: Probabilidad implícita
        
        Returns:
            Texto de recomendación
        """
        if status == EVStatus.NEGATIVE:
            return (
                f"❌ SIN +EV: Probabilidad predicha ({predicted_prob:.1%}) "
                f"es menor que implícita ({implied_prob:.1%}). "
                f"Evitar esta apuesta."
            )
        
        if status == EVStatus.SKIPPED:
            return (
                f"⚠️ +EV BAJO ({ev_percent*100:.1f}%): Aunque técnicamente positivo, "
                f"está por debajo del umbral mínimo recomendado "
                f"({self.bot_config.min_ev_threshold*100:.1f}%). Considerar con precaución."
            )
        
        if status == EVStatus.POSITIVE:
            edge = (predicted_prob - implied_prob) / implied_prob
            return (
                f"✅ +EV DETECTADO (+{ev_percent*100:.1f}%): "
                f"Tu ventaja real es {edge*100:.1f}% sobre la cuota de mercado. "
                f"A largo plazo, apuestas con este +EV son rentables."
            )
        
        return "Sin recomendación disponible."
    
    def _calculate_confidence(self, predicted_prob: float,
                              implied_prob: float,
                              status: EVStatus) -> float:
        """
        Calcular nivel de confianza (0-1).
        Basado en: diferencia de probabilidades y status.
        
        Args:
            predicted_prob: Probabilidad predicha
            implied_prob: Probabilidad implícita
            status: Status del análisis
        
        Returns:
            Confianza (0.0 a 1.0)
        """
        if status != EVStatus.POSITIVE:
            return 0.3  # Baja confianza si no hay +EV
        
        # Confianza basada en diferencia de probabilidades
        prob_diff = abs(predicted_prob - implied_prob)
        
        # Normalizar a rango [0, 1]
        # Máxima diferencia razonable: 0.3 (30%)
        confidence = min(prob_diff / 0.3, 1.0)
        
        # Aplicar factor de sanidad: probabilidades extremas = baja confianza
        if predicted_prob < 0.1 or predicted_prob > 0.9:
            confidence *= 0.7
        
        return confidence


class OddsService:
    """
    Servicio para análisis de cuotas.
    Compara cuotas entre bookmakers y detecta discrepancias.
    """
    
    def __init__(self):
        self.logger = logger
        self.ev_calc = EVCalculator()
    
    def find_best_odds(self, odds_list: list[OddsPair]) -> Optional[OddsPair]:
        """
        Encontrar la mejor cuota de una lista.
        
        Args:
            odds_list: Lista de OddsPair
        
        Returns:
            OddsPair con máxima cuota, o None si lista vacía
        """
        if not odds_list:
            return None
        
        best_odds = max(odds_list, key=lambda x: x.odds_value)
        
        self.logger.debug(
            f"Mejor cuota encontrada: {best_odds.odds_value} "
            f"en {best_odds.bookmaker}"
        )
        
        return best_odds
    
    def compare_bookmakers(self, odds_list: list[OddsPair]) -> dict:
        """
        Comparar cuotas entre bookmakers.
        
        Args:
            odds_list: Lista de OddsPair del mismo tipo
        
        Returns:
            Dict con análisis comparativo
        """
        if not odds_list:
            return {}
        
        bookmakers = {}
        for odds in odds_list:
            if odds.bookmaker not in bookmakers:
                bookmakers[odds.bookmaker] = odds.odds_value
        
        max_odds = max(bookmakers.values())
        min_odds = min(bookmakers.values())
        spread = max_odds - min_odds
        
        return {
            'bookmakers': bookmakers,
            'best_odds': max_odds,
            'worst_odds': min_odds,
            'spread': spread,
            'best_bookmaker': max(bookmakers, key=bookmakers.get),
        }


class PredictionService:
    """
    Servicio para gestionar predicciones de modelos.
    """
    
    def __init__(self):
        self.logger = logger
    
    def validate_prediction(self, prediction) -> bool:
        """
        Validar que una predicción sea válida.
        
        Args:
            prediction: Prediction a validar
        
        Returns:
            True si es válida
        """
        if not 0 <= prediction.predicted_probability <= 1:
            self.logger.warning(
                f"Probabilidad inválida: {prediction.predicted_probability}"
            )
            return False
        
        return True
    
    def merge_predictions(self, predictions: list[Prediction]) -> Prediction:
        """
        Fusionar múltiples predicciones en una sola.
        Promedia probabilidades y toma confianza mínima.
        
        Args:
            predictions: Lista de Prediction
        
        Returns:
            Prediction fusionada
        """
        if not predictions:
            raise ValueError("Lista de predicciones vacía")
        
        avg_prob = sum(p.predicted_probability for p in predictions) / len(predictions)
        min_confidence = min(p.confidence for p in predictions)
        
        # Usar primera predicción como base
        base = predictions[0]
        
        merged = Prediction(
            match_id=base.match_id,
            bet_type=base.bet_type,
            predicted_probability=avg_prob,
            confidence=min_confidence,
            model_version=f"merged_{len(predictions)}_models",
            features_used={}
        )
        
        self.logger.info(
            f"Predicciones fusionadas: {len(predictions)} modelos, "
            f"prob={avg_prob:.1%}, conf={min_confidence.value}"
        )
        
        return merged
