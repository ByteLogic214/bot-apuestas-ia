"""
Orquestador principal: analiza partidos y genera oportunidades de apuestas.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from src.core.config import get_config
from src.core.exceptions import ApuestasException
from src.domain.models import (
    Match, OddsPair, Prediction, BettingOpportunity, AnalysisReport
)
from src.domain.enums import EVStatus
from src.infrastructure.api import (
    OddsAPIClient, FootballAPIClient, GeminiAPIClient, TelegramAPIClient
)
from src.infrastructure.cache import MemoryCache
from src.infrastructure.data import DataManager, ModelLoader
from src.application.services.ev_calculator import (
    EVCalculator, OddsService, PredictionService
)

logger = logging.getLogger(__name__)


class AnalyzeMatchesUseCase:
    """
    Caso de uso principal: analizar partidos y detectar +EV.
    Orquesta todos los servicios e infraestructura.
    """
    
    def __init__(self):
        """Inicializar dependencias."""
        self.config = get_config()
        self.bot_config = self.config.get_bot_config()
        
        # Clientes API
        self.odds_api = OddsAPIClient()
        self.football_api = FootballAPIClient()
        self.gemini_api = GeminiAPIClient()
        self.telegram_api = TelegramAPIClient()
        
        # Infraestructura
        self.cache = MemoryCache(default_ttl=self.bot_config.cache_ttl_seconds)
        self.data_manager = DataManager()
        self.model_loader = ModelLoader()
        
        # Servicios
        self.ev_calculator = EVCalculator()
        self.odds_service = OddsService()
        self.prediction_service = PredictionService()
    
    def execute(self) -> AnalysisReport:
        """
        Ejecutar análisis completo de partidos.
        
        Returns:
            AnalysisReport con resultados
        """
        start_time = datetime.now()
        cycle_id = str(uuid.uuid4())[:8]
        
        logger.info(f"Iniciando ciclo de análisis {cycle_id}")
        
        opportunities = []
        errors = []
        matches_analyzed = 0
        
        try:
            # 1. Obtener partidos del Mundial
            matches = self._get_world_cup_matches()
            
            if not matches:
                logger.warning("No se encontraron partidos para analizar")
                return AnalysisReport(
                    cycle_id=cycle_id,
                    timestamp=start_time,
                    matches_analyzed=0,
                    opportunities_found=[],
                    errors=["No hay partidos disponibles"]
                )
            
            logger.info(f"Partidos cargados: {len(matches)}")
            
            # 2. Obtener cuotas
            odds_data = self.odds_api.get_world_cup_odds()
            logger.info(f"Cuotas obtenidas: {len(odds_data)} partidos")
            
            # 3. Analizar cada partido
            for match in matches:
                try:
                    match_opportunities = self._analyze_match(
                        match=match,
                        odds_by_match=odds_data
                    )
                    
                    opportunities.extend(match_opportunities)
                    matches_analyzed += 1
                
                except Exception as e:
                    error_msg = f"Error analizando {match.match_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # 4. Enviar alertas
            alerts_sent = 0
            for opp in opportunities:
                if opp.is_positive_ev:
                    try:
                        self.telegram_api.send_opportunity_alert(opp)
                        alerts_sent += 1
                    except Exception as e:
                        logger.error(f"Error enviando alerta: {str(e)}")
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            report = AnalysisReport(
                cycle_id=cycle_id,
                timestamp=start_time,
                matches_analyzed=matches_analyzed,
                opportunities_found=opportunities,
                errors=errors,
                processing_time_ms=elapsed_ms
            )
            
            logger.info(
                f"Ciclo {cycle_id} completado: "
                f"{matches_analyzed} partidos, "
                f"{len(opportunities)} oportunidades, "
                f"{alerts_sent} alertas enviadas "
                f"({elapsed_ms:.0f}ms)"
            )
            
            return report
        
        except Exception as e:
            logger.critical(f"Error crítico en ciclo: {str(e)}")
            return AnalysisReport(
                cycle_id=cycle_id,
                timestamp=start_time,
                matches_analyzed=matches_analyzed,
                opportunities_found=opportunities,
                errors=errors + [f"Error crítico: {str(e)}"],
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
    
    def _get_world_cup_matches(self) -> List[Match]:
        """
        Obtener partidos del Mundial 2026.
        
        Returns:
            Lista de Match
        """
        try:
            # Cargar datos de CSV
            df = self.data_manager.load_csv(
                'dataset_mundial2026_ml_actualizado.csv'
            )
            
            matches = []
            
            for _, row in df.iterrows():
                try:
                    # Parsear datos del CSV
                    from datetime import datetime as dt
                    
                    match = Match(
                        match_id=f"{row['Equipo_Local']}_{row['Equipo_Visitante']}",
                        home_team=self.football_api.get_team_stats(row['Equipo_Local']) or 
                                   type('Team', (), {
                                       'name': row['Equipo_Local'],
                                       'fifa_ranking': int(row.get('Ranking_FIFA_Local', 100)),
                                       'elo_rating': float(row.get('Posecion_Local', 50))
                                   })(),
                        away_team=self.football_api.get_team_stats(row['Equipo_Visitante']) or
                                   type('Team', (), {
                                       'name': row['Equipo_Visitante'],
                                       'fifa_ranking': int(row.get('Ranking_FIFA_Visitante', 100)),
                                       'elo_rating': float(row.get('Posecion_Local', 50))
                                   })(),
                        match_date=dt.fromisoformat(row['Fecha']),
                        phase=row['Tipo_Partido']
                    )
                    
                    matches.append(match)
                
                except Exception as e:
                    logger.warning(f"Error parseando partido: {str(e)}")
            
            return matches
        
        except Exception as e:
            raise ApuestasException(f"Error cargando partidos: {str(e)}")
    
    def _analyze_match(self, match: Match,
                      odds_by_match: dict) -> List[BettingOpportunity]:
        """
        Analizar un partido individual.
        
        Args:
            match: Match a analizar
            odds_by_match: Dict de cuotas por partido
        
        Returns:
            Lista de BettingOpportunity encontradas
        """
        opportunities = []
        
        # Obtener cuotas para este partido
        match_odds = odds_by_match.get(match.match_id, [])
        
        if not match_odds:
            logger.debug(f"Sin cuotas para {match.match_id}")
            return opportunities
        
        # Agrupar cuotas por tipo de apuesta
        odds_by_type = {}
        for odds in match_odds:
            if odds.bet_type not in odds_by_type:
                odds_by_type[odds.bet_type] = []
            odds_by_type[odds.bet_type].append(odds)
        
        # Analizar cada tipo de apuesta
        for bet_type, odds_list in odds_by_type.items():
            try:
                # Encontrar mejor cuota
                best_odds = self.odds_service.find_best_odds(odds_list)
                
                if not best_odds:
                    continue
                
                # Generar predicción con Gemini
                prediction = self.gemini_api.analyze_ev(
                    match=match,
                    odds_pair=best_odds
                )
                
                # Calcular +EV
                ev_analysis = self.ev_calculator.calculate(
                    odds_pair=best_odds,
                    predicted_prob=prediction.predicted_probability
                )
                
                # Crear oportunidad
                opportunity = BettingOpportunity(
                    opportunity_id=str(uuid.uuid4())[:8],
                    match=match,
                    odds_pair=best_odds,
                    prediction=prediction,
                    ev_analysis=ev_analysis,
                    alert_sent=False
                )
                
                opportunities.append(opportunity)
                
                logger.info(
                    f"Oportunidad analizada: {match.match_id} "
                    f"{bet_type.value} @ {best_odds.odds_value} = "
                    f"+{ev_analysis.ev_percent*100:.1f}%"
                )
            
            except Exception as e:
                logger.error(
                    f"Error analizando {match.match_id} {bet_type.value}: {str(e)}"
                )
        
        return opportunities
