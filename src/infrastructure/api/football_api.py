"""
Cliente para API-Football (RapidAPI).
Obtiene estadísticas históricas y datos de equipos para análisis.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from src.infrastructure.api.base import HTTPClient, HTTPResponse
from src.core.config import get_config
from src.core.exceptions import FootballAPIException
from src.domain.models import Team, Match
from src.domain.enums import MatchPhase

logger = logging.getLogger(__name__)


class FootballAPIClient(HTTPClient):
    """
    Cliente para API-Football con métodos específicos.
    Requiere RapidAPI key en headers.
    """
    
    def __init__(self):
        config = get_config()
        api_config = config.get_api_config()
        bot_config = config.get_bot_config()
        
        super().__init__(
            base_url=api_config.FOOTBALL_API_BASE,
            timeout=bot_config.api_timeout_seconds,
            max_retries=bot_config.max_retries
        )
        
        self.api_key = api_config.football_api_key
    
    def get_team_stats(self, team_name: str) -> Optional[Team]:
        """
        Obtener estadísticas de un equipo.
        
        Args:
            team_name: Nombre del equipo
        
        Returns:
            Team con ranking FIFA y ELO, o None si no existe
        
        Raises:
            FootballAPIException: Error en API
        """
        try:
            headers = self._get_headers()
            
            params = {
                'name': team_name,
                'season': 2026
            }
            
            response = self.get('/teams', params=params, headers=headers)
            
            if not response.is_success or not response.data.get('response'):
                logger.warning(f"Equipo no encontrado: {team_name}")
                return None
            
            team_data = response.data['response'][0]
            
            # Extraer datos (valores por defecto si no existen)
            team = Team(
                name=team_data.get('name', team_name),
                fifa_ranking=team_data.get('statistics', {}).get('rank', 100),
                elo_rating=team_data.get('statistics', {}).get('elo', 1600.0)
            )
            
            logger.info(f"Stats obtenidos para {team.name}: FIFA={team.fifa_ranking}, ELO={team.elo_rating}")
            
            return team
        
        except Exception as e:
            raise FootballAPIException(f"Error en FootballAPI: {str(e)}")
    
    def get_head_to_head(self, team1: str, team2: str,
                        limit: int = 10) -> List[Dict]:
        """
        Obtener historial de enfrentamientos entre dos equipos.
        
        Args:
            team1: Primer equipo
            team2: Segundo equipo
            limit: Número de partidos a recuperar
        
        Returns:
            Lista de resultados históricos
        
        Raises:
            FootballAPIException: Error en API
        """
        try:
            headers = self._get_headers()
            
            params = {
                'h2h': f"{team1}-{team2}",
                'last': limit
            }
            
            response = self.get('/fixtures', params=params, headers=headers)
            
            if not response.is_success:
                logger.warning(
                    f"H2H no encontrado para {team1} vs {team2}"
                )
                return []
            
            return response.data.get('response', [])
        
        except Exception as e:
            raise FootballAPIException(f"Error obteniendo H2H: {str(e)}")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Construir headers para RapidAPI.
        
        Returns:
            Dict con headers requeridos
        """
        return {
            'X-RapidAPI-Key': self.api_key,
            'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
        }
