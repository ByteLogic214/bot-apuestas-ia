"""Tests para validar funcionalidad de servicios críticos."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.domain.models import Match, OddsPair, Team, Prediction
from src.domain.enums import BetType, MatchPhase, PredictionConfidence, EVStatus
from src.application.services.ev_calculator import EVCalculator
from src.core.exceptions import ValidationException


class TestEVCalculator:
    """Tests para cálculo de Valor Esperado."""
    
    @pytest.fixture
    def ev_calc(self):
        return EVCalculator()
    
    @pytest.fixture
    def sample_odds(self):
        return OddsPair(
            bet_type=BetType.WIN_HOME,
            odds_value=2.50,
            bookmaker="Bet365",
            updated_at=datetime.now()
        )
    
    def test_calculate_positive_ev(self, ev_calc, sample_odds):
        """Test cálculo de +EV positivo."""
        # Si predicción es 45% y cuota es 2.50 (40% implícita)
        # EV = (0.45 * 2.50) - 1 = 1.125 - 1 = +0.125 = +12.5%
        
        analysis = ev_calc.calculate(
            odds_pair=sample_odds,
            predicted_prob=0.45
        )
        
        assert analysis.status == EVStatus.POSITIVE
        assert analysis.ev_percent > 0
        assert analysis.confidence > 0.5
    
    def test_calculate_negative_ev(self, ev_calc, sample_odds):
        """Test cálculo de -EV negativo."""
        # Si predicción es 30% y cuota es 2.50 (40% implícita)
        # EV = (0.30 * 2.50) - 1 = 0.75 - 1 = -0.25 = -25%
        
        analysis = ev_calc.calculate(
            odds_pair=sample_odds,
            predicted_prob=0.30
        )
        
        assert analysis.status == EVStatus.NEGATIVE
        assert analysis.ev_percent < 0
        assert analysis.confidence < 0.5
    
    def test_validate_invalid_odds(self, ev_calc):
        """Test validación de cuota inválida."""
        invalid_odds = OddsPair(
            bet_type=BetType.WIN_HOME,
            odds_value=0.5,  # Inválido: < 1.0
            bookmaker="Invalid",
            updated_at=datetime.now()
        )
        
        with pytest.raises(ValidationException):
            ev_calc.calculate(
                odds_pair=invalid_odds,
                predicted_prob=0.5
            )
    
    def test_validate_invalid_probability(self, ev_calc, sample_odds):
        """Test validación de probabilidad inválida."""
        with pytest.raises(ValidationException):
            ev_calc.calculate(
                odds_pair=sample_odds,
                predicted_prob=1.5  # Inválido: > 1.0
            )


class TestOddsService:
    """Tests para servicio de cuotas."""
    
    @pytest.fixture
    def odds_list(self):
        return [
            OddsPair(BetType.WIN_HOME, 2.10, "Bet365", datetime.now()),
            OddsPair(BetType.WIN_HOME, 2.05, "1xBet", datetime.now()),
            OddsPair(BetType.WIN_HOME, 2.20, "Betfair", datetime.now()),
        ]
    
    def test_find_best_odds(self, odds_list):
        """Test encontrar mejor cuota."""
        from src.application.services.ev_calculator import OddsService
        
        service = OddsService()
        best = service.find_best_odds(odds_list)
        
        assert best.odds_value == 2.20
        assert best.bookmaker == "Betfair"
    
    def test_find_best_odds_empty(self):
        """Test con lista vacía."""
        from src.application.services.ev_calculator import OddsService
        
        service = OddsService()
        result = service.find_best_odds([])
        
        assert result is None


class TestMemoryCache:
    """Tests para sistema de cache."""
    
    def test_cache_set_get(self):
        """Test set y get básico."""
        from src.infrastructure.cache import MemoryCache
        
        cache = MemoryCache(default_ttl=60)
        cache.set("key1", "value1")
        
        result = cache.get("key1")
        
        assert result == "value1"
    
    def test_cache_miss(self):
        """Test cache miss."""
        from src.infrastructure.cache import MemoryCache
        
        cache = MemoryCache()
        result = cache.get("nonexistent", default="default_value")
        
        assert result == "default_value"
    
    def test_cache_statistics(self):
        """Test estadísticas de cache."""
        from src.infrastructure.cache import MemoryCache
        
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.get_stats()
        
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate_percent'] == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
