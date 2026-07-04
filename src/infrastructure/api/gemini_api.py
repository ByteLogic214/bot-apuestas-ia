"""
Cliente para Google Gemini AI.
Utiliza el modelo generativo para análisis de +EV con lógica probabilista.
"""

import logging
from typing import Optional, Dict
from datetime import datetime
import json

from src.infrastructure.api.base import HTTPClient, HTTPResponse
from src.core.config import get_config
from src.core.exceptions import GeminiAPIException
from src.domain.models import Prediction, Match, OddsPair
from src.domain.enums import PredictionConfidence, BetType

logger = logging.getLogger(__name__)


class GeminiAPIClient(HTTPClient):
    """
    Cliente para Google Gemini con prompts cuantitativos.
    Genera predicciones probabilistas para análisis +EV.
    """
    
    def __init__(self):
        config = get_config()
        api_config = config.get_api_config()
        bot_config = config.get_bot_config()
        
        super().__init__(
            base_url=api_config.GEMINI_API_BASE,
            timeout=bot_config.api_timeout_seconds,
            max_retries=bot_config.max_retries
        )
        
        self.api_key = api_config.gemini_api_key
        self.model = "gemini-pro"  # Modelo utilizado
    
    def analyze_ev(self, match: Match, odds_pair: OddsPair,
                   historical_data: Optional[Dict] = None) -> Prediction:
        """
        Analizar Valor Esperado (+EV) usando Gemini.
        
        Args:
            match: Información del partido
            odds_pair: Cuota a analizar
            historical_data: Datos históricos del enfrentamiento
        
        Returns:
            Prediction con probabilidad y confianza
        
        Raises:
            GeminiAPIException: Error en API o análisis
        """
        try:
            # Construir prompt con contexto cuantitativo
            prompt = self._build_analysis_prompt(
                match=match,
                odds_pair=odds_pair,
                historical_data=historical_data
            )
            
            response = self._generate(
                prompt=prompt,
                temperature=0.3  # Bajo: respuestas más deterministas
            )
            
            # Parsear respuesta para extraer probabilidad
            probability, confidence = self._parse_probability_response(
                response.data
            )
            
            prediction = Prediction(
                match_id=match.match_id,
                bet_type=odds_pair.bet_type,
                predicted_probability=probability,
                confidence=self._map_confidence_level(confidence),
                model_version="gemini-pro-v1",
                features_used={
                    'home_ranking': float(match.home_team.fifa_ranking),
                    'away_ranking': float(match.away_team.fifa_ranking),
                    'home_elo': match.home_team.elo_rating,
                    'away_elo': match.away_team.elo_rating,
                }
            )
            
            logger.info(
                f"Predicción generada para {match.match_id}: "
                f"prob={probability:.2%}, confidence={confidence}"
            )
            
            return prediction
        
        except Exception as e:
            raise GeminiAPIException(f"Error en análisis Gemini: {str(e)}")
    
    def _build_analysis_prompt(self, match: Match, odds_pair: OddsPair,
                               historical_data: Optional[Dict]) -> str:
        """
        Construir prompt cuantitativo para Gemini.
        
        Args:
            match: Datos del partido
            odds_pair: Cuota a analizar
            historical_data: Contexto histórico
        
        Returns:
            Prompt formateado
        """
        prompt = f"""
Análisis cuantitativo de Valor Esperado (+EV) para apuesta deportiva.

DATA DEL PARTIDO:
- Fecha: {match.match_date.isoformat()}
- Local: {match.home_team.name} (FIFA Rank: {match.home_team.fifa_ranking}, ELO: {match.home_team.elo_rating})
- Visitante: {match.away_team.name} (FIFA Rank: {match.away_team.fifa_ranking}, ELO: {match.away_team.elo_rating})
- Fase: {match.phase.value}

DATOS DE APUESTA:
- Tipo de apuesta: {odds_pair.bet_type.value}
- Cuota de mercado: {odds_pair.odds_value}
- Bookmaker: {odds_pair.bookmaker}
- Probabilidad implícita: {1/odds_pair.odds_value:.2%}

INSTRUCCIONES:
1. Analiza la probabilidad real basada en rankings FIFA y ELO
2. Considera ventaja local (12% histórica)
3. Genera predicción de probabilidad en escala 0-1
4. Indica confianza: muy_baja|baja|media|alta|muy_alta
5. Responde SOLO en formato JSON:
{{
    "predicted_probability": 0.XX,
    "confidence": "alta",
    "reasoning": "explicación breve"
}}

RESPUESTA:
"""
        return prompt
    
    def _generate(self, prompt: str, temperature: float = 0.3) -> HTTPResponse:
        """
        Llamar a Gemini API para generar contenido.
        
        Args:
            prompt: Prompt a procesar
            temperature: Control de aleatoriedad (0-1)
        
        Returns:
            HTTPResponse con contenido generado
        
        Raises:
            GeminiAPIException: Error en API
        """
        try:
            params = {
                'key': self.api_key
            }
            
            json_data = {
                'contents': [{
                    'parts': [{'text': prompt}]
                }],
                'generationConfig': {
                    'temperature': temperature,
                    'maxOutputTokens': 500
                }
            }
            
            response = self.post(
                f"/gemini-pro:generateContent",
                json_data=json_data,
                params=params
            )
            
            if not response.is_success:
                raise GeminiAPIException(
                    f"Error Gemini API: {response.status_code}"
                )
            
            return response
        
        except Exception as e:
            raise GeminiAPIException(f"Error en generateContent: {str(e)}")
    
    @staticmethod
    def _parse_probability_response(data: Dict) -> tuple[float, str]:
        """
        Parsear respuesta JSON de Gemini.
        
        Args:
            data: Respuesta de API
        
        Returns:
            Tupla (probabilidad, confianza)
        """
        try:
            # Extraer texto de la respuesta
            text = data.get('candidates', [{}])[0].get('content', {}).get(
                'parts', [{}]
            )[0].get('text', '{}')
            
            # Parsear JSON embebido en texto
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                parsed = json.loads(json_str)
                
                probability = float(parsed.get('predicted_probability', 0.5))
                confidence = parsed.get('confidence', 'media')
                
                return probability, confidence
        
        except Exception as e:
            logger.warning(f"Error parseando respuesta Gemini: {str(e)}")
        
        # Valores por defecto en caso de error
        return 0.5, 'baja'
    
    @staticmethod
    def _map_confidence_level(confidence_str: str) -> PredictionConfidence:
        """
        Mapear string de confianza a enum.
        
        Args:
            confidence_str: String de confianza
        
        Returns:
            PredictionConfidence enum
        """
        mapping = {
            'muy_baja': PredictionConfidence.VERY_LOW,
            'baja': PredictionConfidence.LOW,
            'media': PredictionConfidence.MEDIUM,
            'alta': PredictionConfidence.HIGH,
            'muy_alta': PredictionConfidence.VERY_HIGH,
        }
        
        return mapping.get(confidence_str.lower(), PredictionConfidence.MEDIUM)
