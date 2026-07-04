"""
Entry point: ejecutar bot manualmente o desde GitHub Actions.
"""

import sys
import logging
from datetime import datetime
import argparse

from src.core import get_logger, get_config
from src.core.exceptions import ApuestasException
from src.application.use_cases.analyze_matches import AnalyzeMatchesUseCase

# Configurar logging
logger = get_logger(__name__, logging.INFO)


def main(args=None):
    """
    Punto de entrada principal.
    Ejecuta ciclo de análisis de partidos.
    """
    try:
        logger.info("="*60)
        logger.info("🏆 Bot de Apuestas IA - Copa Mundial FIFA 2026")
        logger.info(f"Inicio: {datetime.now().isoformat()}")
        logger.info("="*60)
        
        # Inicializar
        config = get_config()
        use_case = AnalyzeMatchesUseCase()
        
        # Ejecutar análisis
        report = use_case.execute()
        
        # Mostrar resultados
        logger.info("\n" + "="*60)
        logger.info("📊 REPORTE DE ANÁLISIS")
        logger.info("="*60)
        logger.info(f"Ciclo ID: {report.cycle_id}")
        logger.info(f"Partidos analizados: {report.matches_analyzed}")
        logger.info(f"Oportunidades encontradas: {len(report.opportunities_found)}")
        logger.info(f"Oportunidades +EV: {len(report.high_confidence_opportunities)}")
        logger.info(f"Tasa de éxito: {report.success_rate:.1f}%")
        logger.info(f"Tiempo de procesamiento: {report.processing_time_ms:.0f}ms")
        
        if report.errors:
            logger.warning(f"Errores encontrados: {len(report.errors)}")
            for error in report.errors:
                logger.warning(f"  - {error}")
        
        logger.info("="*60)
        
        return 0
    
    except ApuestasException as e:
        logger.error(f"Error de aplicación: {str(e)}")
        return 1
    
    except Exception as e:
        logger.critical(f"Error inesperado: {str(e)}", exc_info=True)
        return 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Bot de Apuestas IA - Análisis de +EV para Mundial 2026'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Activar modo debug (verbose logging)'
    )
    
    args = parser.parse_args()
    
    sys.exit(main(args))
