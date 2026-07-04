"""
Gestor de datos con Pandas optimizado para acceso rápido.
Carga CSVs con índices y cacheo para O(1) lookups.
"""

import logging
import os
from typing import Optional, List, Dict, Any
from pathlib import Path
import pandas as pd

from src.core.config import get_config
from src.core.exceptions import DataException
from src.infrastructure.cache.memory_cache import MemoryCache

logger = logging.getLogger(__name__)


class DataManager:
    """
    Gestor centralizado de datos con cache.
    Carga CSVs una sola vez y reutiliza en memoria.
    """
    
    def __init__(self, cache_ttl: int = 3600):
        """
        Inicializar gestor de datos.
        
        Args:
            cache_ttl: TTL del cache en segundos
        """
        self.config = get_config()
        self.data_dir = self.config.get_data_config().data_dir
        self.cache = MemoryCache(default_ttl=cache_ttl)
        self._dataframes: Dict[str, pd.DataFrame] = {}
        self._indices: Dict[str, Dict[str, int]] = {}  # Índices para lookups
    
    def load_csv(self, filename: str, index_column: Optional[str] = None) -> pd.DataFrame:
        """
        Cargar CSV una sola vez y cachear.
        
        Args:
            filename: Nombre del archivo en data_dir
            index_column: Columna para crear índice
        
        Returns:
            DataFrame cargado
        
        Raises:
            DataException: Si el archivo no existe
        """
        filepath = os.path.join(self.data_dir, filename)
        
        # Verificar si ya está cacheado
        if filename in self._dataframes:
            logger.debug(f"Usando DataFrame cacheado: {filename}")
            return self._dataframes[filename]
        
        # Verificar existencia de archivo
        if not os.path.exists(filepath):
            raise DataException(
                f"Archivo no encontrado: {filepath}"
            )
        
        try:
            logger.info(f"Cargando CSV: {filename}")
            
            df = pd.read_csv(filepath, encoding='utf-8')
            
            # Crear índice si se especifica
            if index_column and index_column in df.columns:
                self._indices[filename] = df.set_index(
                    index_column
                ).to_dict('index')
                logger.debug(
                    f"Índice creado en {index_column} "
                    f"({len(self._indices[filename])} entradas)"
                )
            
            # Cachear DataFrame
            self._dataframes[filename] = df
            
            logger.info(
                f"CSV cargado: {filename} "
                f"({len(df)} filas, {len(df.columns)} columnas)"
            )
            
            return df
        
        except Exception as e:
            raise DataException(f"Error cargando {filename}: {str(e)}")
    
    def get_by_index(self, filename: str, index_column: str,
                     key: Any) -> Optional[Dict]:
        """
        Buscar fila por valor de columna usando índice.
        Complejidad: O(1) en lugar de O(n).
        
        Args:
            filename: Nombre del archivo
            index_column: Columna de índice
            key: Valor a buscar
        
        Returns:
            Dict con la fila encontrada, o None
        
        Raises:
            DataException: Si el archivo no existe
        """
        # Cargar y crear índice si es necesario
        self.load_csv(filename, index_column=index_column)
        
        index_key = filename
        
        if index_key not in self._indices:
            raise DataException(
                f"No hay índice para {index_column} en {filename}"
            )
        
        return self._indices[index_key].get(key)
    
    def search_column(self, filename: str, column: str,
                      value: Any) -> pd.DataFrame:
        """
        Buscar filas donde columna = valor.
        Complejidad: O(n) pero con optimizaciones de Pandas.
        
        Args:
            filename: Nombre del archivo
            column: Nombre de la columna
            value: Valor a buscar
        
        Returns:
            DataFrame filtrado
        
        Raises:
            DataException: Si el archivo o columna no existe
        """
        df = self.load_csv(filename)
        
        if column not in df.columns:
            raise DataException(
                f"Columna no encontrada: {column} en {filename}"
            )
        
        return df[df[column] == value]
    
    def aggregate(self, filename: str, group_by: str,
                  agg_func: str = 'mean') -> pd.DataFrame:
        """
        Agregar datos por columna.
        
        Args:
            filename: Nombre del archivo
            group_by: Columna para agrupar
            agg_func: Función de agregación (mean, sum, count, etc)
        
        Returns:
            DataFrame agregado
        
        Raises:
            DataException: Si la columna no existe
        """
        df = self.load_csv(filename)
        
        if group_by not in df.columns:
            raise DataException(
                f"Columna no encontrada: {group_by} en {filename}"
            )
        
        return df.groupby(group_by).agg(agg_func)
    
    def get_memoria_usage(self) -> Dict[str, int]:
        """
        Obtener uso de memoria de DataFrames cacheados.
        
        Returns:
            Dict con {filename: bytes}
        """
        usage = {}
        
        for filename, df in self._dataframes.items():
            usage[filename] = int(df.memory_usage(deep=True).sum())
        
        return usage
    
    def clear_cache(self) -> None:
        """Limpiar todos los DataFrames e índices cacheados."""
        count = len(self._dataframes)
        self._dataframes.clear()
        self._indices.clear()
        self.cache.clear()
        logger.info(f"Data cache cleared: {count} DataFrames eliminados")
