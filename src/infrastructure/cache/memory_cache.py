"""
Sistema de cache en memoria con TTL (Time To Live).
Optimiza lookups de datos frecuentes: O(1) en lugar de O(n).
"""

import time
import logging
from typing import Any, Optional, Dict, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Entrada individual del cache con metadata."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 1800  # 30 minutos por defecto
    
    @property
    def is_expired(self) -> bool:
        """Verificar si la entrada ha expirado."""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds
    
    @property
    def remaining_ttl(self) -> int:
        """Segundos restantes hasta expiración."""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return max(0, int(self.ttl_seconds - elapsed))


class MemoryCache:
    """
    Cache en memoria thread-safe con expiración automática.
    Complejidad: O(1) para get/set, O(n) para cleanup.
    """
    
    def __init__(self, default_ttl: int = 1800):
        """
        Inicializar cache.
        
        Args:
            default_ttl: TTL por defecto en segundos
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._locks: Dict[str, Lock] = {}  # Locks por clave
        self.default_ttl = default_ttl
        self._global_lock = Lock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtener valor del cache.
        
        Args:
            key: Clave a buscar
            default: Valor por defecto si no existe
        
        Returns:
            Valor cacheado o default
        """
        with self._global_lock:
            if key not in self._cache:
                self.misses += 1
                return default
            
            entry = self._cache[key]
            
            # Verificar expiración
            if entry.is_expired:
                del self._cache[key]
                self.misses += 1
                logger.debug(f"Cache miss (expirado): {key}")
                return default
            
            self.hits += 1
            logger.debug(
                f"Cache hit: {key} (TTL restante: {entry.remaining_ttl}s)"
            )
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Establecer valor en cache.
        
        Args:
            key: Clave
            value: Valor a cachear
            ttl: TTL personalizado (None = usar default)
        """
        ttl = ttl or self.default_ttl
        
        with self._global_lock:
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl
            )
            self._cache[key] = entry
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
    
    def delete(self, key: str) -> bool:
        """
        Eliminar entrada del cache.
        
        Args:
            key: Clave a eliminar
        
        Returns:
            True si se eliminó, False si no existía
        """
        with self._global_lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache delete: {key}")
                return True
            return False
    
    def clear(self) -> None:
        """Limpiar todo el cache."""
        with self._global_lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entradas eliminadas")
    
    def cleanup_expired(self) -> int:
        """
        Eliminar entradas expiradas (garbage collection).
        
        Returns:
            Número de entradas eliminadas
        """
        with self._global_lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(
                    f"Cache cleanup: {len(expired_keys)} entradas expiradas eliminadas"
                )
            
            return len(expired_keys)
    
    def get_or_fetch(self, key: str, fetch_fn: Callable,
                     ttl: Optional[int] = None) -> Any:
        """
        Obtener del cache o generar/obtener usando función.
        Patrón común para evitar cálculos repetidos.
        
        Args:
            key: Clave
            fetch_fn: Función que obtiene el valor si no existe
            ttl: TTL personalizado
        
        Returns:
            Valor cacheado o recientemente obtenido
        
        Ejemplo:
            odds = cache.get_or_fetch(
                'odds_match_123',
                lambda: odds_api.get_odds('match_123'),
                ttl=900
            )
        """
        # Intentar obtener del cache primero
        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value
        
        # Si no existe, generar usando fetch_fn
        logger.debug(f"Cache miss - fetching: {key}")
        value = fetch_fn()
        
        # Cachear el resultado
        self.set(key, value, ttl)
        
        return value
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas del cache.
        
        Returns:
            Dict con métricas
        """
        with self._global_lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'entries': len(self._cache),
                'hits': self.hits,
                'misses': self.misses,
                'total_requests': total_requests,
                'hit_rate_percent': hit_rate,
            }
    
    def __len__(self) -> int:
        """Obtener número de entradas en cache."""
        with self._global_lock:
            return len(self._cache)
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"MemoryCache({stats['entries']} entries, "
            f"{stats['hit_rate_percent']:.1f}% hit rate)"
        )
