"""
Cliente para The Odds API.
Obtiene cuotas en tiempo real de bookmakers para el Mundial 2026.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from src.infrastructure.api.base import HTTPClient, HTTPResponse
from src.core.config import get_config
from src.core.exceptions import OddsAPIException
from src.domain.models import OddsPair
from src.domain.enums import BetType

logger = logging.getLogger(__name__)


class OddsAPIClient(HTTPClient):
    """
    Cliente para The Odds API con métodos específicos.
    Soporta múltiples bookmakers y mercados.
    """
    
    def __init__(self):
        config = get_config()
        api_config = config.get_api_config()
        bot_config = config.get_bot_config()
        
        super().__init__(
            base_url=api_config.ODDS_API_BASE,
            timeout=bot_config.api_timeout_seconds,
            max_retries=bot_config.max_retries
        )
        
        self.api_key = api_config.odds_api_key
    
    def get_world_cup_odds(self, sport: str = "soccer_fifa_world_cup",
                           market: str = "h2h") -> Dict[str, List[OddsPair]]:
        """
        Obtener cuotas del Mundial 2026 agrupadas por partido.
        
        Args:
            sport: Sport code (default: soccer_fifa_world_cup)
            market: Tipo de mercado (h2h=1X2, spreads, totals)
        
        Returns:
            Dict con {match_id: [OddsPair, ...]}
        
        Raises:
            OddsAPIException: Error al obtener datos
        """
        try:
            params = {
                'api_key': self.api_key,
                'sport': sport,
                'markets': market,
                'regions': 'us,eu',  # Bookmakers USA y Europa
                'oddsFormat': 'decimal'
            }
            
            response = self.get('/sports', params=params)
            
            if not response.is_success:
                raise OddsAPIException(
                    f"Error al obtener cuotas: {response.status_code}"
                )
            
            # Parsear y convertir a OddsPair
            odds_by_match = self._parse_odds_response(response.data)
            
            logger.info(f"Cuotas obtenidas para {len(odds_by_match)} partidos")
            
            return odds_by_match
        
        except Exception as e:
            raise OddsAPIException(f"Error en OddsAPI: {str(e)}")
    
    def _parse_odds_response(self, data: Dict) -> Dict[str, List[OddsPair]]:
        """
        Parsear respuesta de The Odds API a OddsPair.
        
        Complejidad: O(n*m) donde n=partidos, m=bookmakers
        Optimización: Usar dict lookup en lugar de búsqueda lineal
        """
        odds_by_match = {}
        
        # Iterar sobre eventos (partidos)
        events = data.get('events', [])
        
        for event in events:
            match_id = event['id']
            bookmakers = event.get('bookmakers', [])
            
            odds_list = []
            
            # Iterar sobre bookmakers
            for bookmaker in bookmakers:
                bookmaker_name = bookmaker['title']
                markets = bookmaker.get('markets', [])
                
                # Buscar mercado 1X2
                for market in markets:
                    if market['key'] == 'h2h':
                        outcomes = market.get('outcomes', [])
                        
                        for outcome in outcomes:
                            # Mapear outcomes a BetType
                            bet_type = self._map_outcome_to_bet_type(
                                outcome['name']
                            )
                            
                            odds_pair = OddsPair(
                                bet_type=bet_type,
                                odds_value=float(outcome['price']),
                                bookmaker=bookmaker_name,
                                updated_at=datetime.now()
                            )
                            
                            odds_list.append(odds_pair)
            
            if odds_list:
                odds_by_match[match_id] = odds_list
        
        return odds_by_match
    
    @staticmethod
    def _map_outcome_to_bet_type(outcome_name: str) -> BetType:
        """
        Mapear nombre de outcome a BetType.
        
        Args:
            outcome_name: Nombre del outcome de la API
        
        Returns:
            BetType correspondiente
        """
        mapping = {
            '1': BetType.WIN_HOME,
            'X': BetType.DRAW,
            '2': BetType.WIN_AWAY,
            'Draw': BetType.DRAW,
            'Over': BetType.UNDER_OVER,
            'Under': BetType.UNDER_OVER,
        }
        
        return mapping.get(outcome_name, BetType.WIN_HOME)
