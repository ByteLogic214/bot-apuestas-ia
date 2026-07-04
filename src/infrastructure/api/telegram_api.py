"""
Cliente para Telegram Bot API.
Envía alertas de apuestas +EV al usuario.
"""

import logging
from typing import Optional
from datetime import datetime

from src.infrastructure.api.base import HTTPClient, HTTPResponse
from src.core.config import get_config
from src.core.exceptions import TelegramAPIException
from src.domain.models import BettingOpportunity

logger = logging.getLogger(__name__)


class TelegramAPIClient(HTTPClient):
    """
    Cliente para Telegram Bot API.
    Envía alertas formateadas de oportunidades +EV.
    """
    
    def __init__(self):
        config = get_config()
        api_config = config.get_api_config()
        
        # Construir URL base: https://api.telegram.org/botTOKEN/
        base_url = f"{api_config.TELEGRAM_API_BASE}{api_config.telegram_token}"
        
        super().__init__(
            base_url=base_url,
            timeout=30,
            max_retries=3
        )
        
        self.chat_id = api_config.telegram_chat_id
    
    def send_opportunity_alert(self, opportunity: BettingOpportunity) -> bool:
        """
        Enviar alerta formateada de oportunidad +EV.
        
        Args:
            opportunity: BettingOpportunity a alertar
        
        Returns:
            True si se envío exitosamente
        
        Raises:
            TelegramAPIException: Error en envío
        """
        try:
            message = self._format_opportunity_message(opportunity)
            
            response = self.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML"
            )
            
            if response.is_success:
                logger.info(
                    f"Alerta enviada para {opportunity.match.match_id} "
                    f"(+{opportunity.edge_percent:.1f}%)"
                )
                return True
            else:
                logger.error(
                    f"Error enviando alerta: {response.status_code}"
                )
                return False
        
        except Exception as e:
            raise TelegramAPIException(f"Error enviando alerta Telegram: {str(e)}")
    
    def send_message(self, chat_id: str, text: str,
                     parse_mode: str = "HTML") -> HTTPResponse:
        """
        Enviar mensaje de texto a Telegram.
        
        Args:
            chat_id: ID del chat
            text: Texto del mensaje
            parse_mode: Formato (HTML, Markdown)
        
        Returns:
            HTTPResponse de Telegram
        
        Raises:
            TelegramAPIException: Error en envío
        """
        try:
            json_data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = self.post('/sendMessage', json_data=json_data)
            
            if not response.is_success:
                raise TelegramAPIException(
                    f"Telegram error {response.status_code}: {response.data}"
                )
            
            return response
        
        except Exception as e:
            raise TelegramAPIException(f"Error en sendMessage: {str(e)}")
    
    @staticmethod
    def _format_opportunity_message(opportunity: BettingOpportunity) -> str:
        """
        Formatear oportunidad como mensaje HTML para Telegram.
        
        Args:
            opportunity: BettingOpportunity a formatear
        
        Returns:
            String HTML con alerta formateada
        """
        match = opportunity.match
        odds = opportunity.odds_pair
        analysis = opportunity.ev_analysis
        prediction = opportunity.prediction
        
        # Formateo HTML con emojis y estilos
        message = f"""
<b>💯 ALERTA +EV DETECTADA</b>

<b>Partido:</b> {match.home_team.name} vs {match.away_team.name}
<b>Fecha:</b> {match.match_date.strftime('%Y-%m-%d %H:%M')}
<b>Fase:</b> {match.phase.value}

<b>💵 Apuesta Recomendada:</b>
  Tipo: {odds.bet_type.value}
  Cuota: {odds.odds_value:.2f}
  Bookmaker: {odds.bookmaker}

<b>💡 Análisis +EV:</b>
  Probabilidad Predicha: {prediction.predicted_probability:.1%}
  Probabilidad Implícita: {1/odds.odds_value:.1%}
  Ventaja (+EV): <code>+{analysis.ev_percent*100:.1f}%</code>
  Confianza: {prediction.confidence.value.upper()}

<b>📚 Razonamiento:</b>
{analysis.recommendation}

<i>Análisis generado: {analysis.analyzed_at.strftime('%H:%M:%S')}</i>
"""
        
        return message
    
    def send_daily_report(self, report_summary: str) -> bool:
        """
        Enviar reporte diario de actividad.
        
        Args:
            report_summary: Resumen del día
        
        Returns:
            True si se envió exitosamente
        """
        try:
            message = f"""
<b>📅 REPORTE DIARIO</b>

{report_summary}

<i>Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
            
            response = self.send_message(
                chat_id=self.chat_id,
                text=message
            )
            
            return response.is_success
        
        except Exception as e:
            logger.error(f"Error en send_daily_report: {str(e)}")
            return False
