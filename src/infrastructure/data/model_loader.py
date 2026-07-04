"""
Cargador de modelos ML (PKL y CBM) con lazy loading.
Optimiza memoria cargando solo cuando se necesita.
"""

import logging
import os
from typing import Any, Optional
import joblib

from src.core.config import get_config
from src.core.exceptions import ModelException

logger = logging.getLogger(__name__)


class ModelLoader:
    """
    Cargador de modelos con lazy loading.
    Evita cargar modelos hasta que se necesiten.
    """
    
    def __init__(self):
        self.config = get_config()
        self.models_dir = self.config.get_data_config().models_dir
        self._models: dict[str, Any] = {}  # Cache de modelos cargados
    
    def load_pkl_model(self, model_name: str) -> Any:
        """
        Cargar modelo PKL (scikit-learn compatible).
        
        Args:
            model_name: Nombre del archivo .pkl
        
        Returns:
            Modelo cargado
        
        Raises:
            ModelException: Si el archivo no existe o falla carga
        """
        # Retornar si ya está cacheado
        if model_name in self._models:
            logger.debug(f"Modelo cacheado: {model_name}")
            return self._models[model_name]
        
        filepath = os.path.join(self.models_dir, model_name)
        
        if not filepath.endswith('.pkl'):
            filepath += '.pkl'
        
        if not os.path.exists(filepath):
            raise ModelException(
                f"Archivo modelo no encontrado: {filepath}"
            )
        
        try:
            logger.info(f"Cargando modelo PKL: {model_name}")
            model = joblib.load(filepath)
            
            # Cachear para futuros usos
            self._models[model_name] = model
            
            logger.info(f"Modelo cargado exitosamente: {model_name}")
            
            return model
        
        except Exception as e:
            raise ModelException(
                f"Error cargando modelo {model_name}: {str(e)}"
            )
    
    def load_cbm_model(self, model_name: str) -> Any:
        """
        Cargar modelo CatBoost (.cbm).
        Requiere biblioteca catboost.
        
        Args:
            model_name: Nombre del archivo .cbm
        
        Returns:
            Modelo CatBoost cargado
        
        Raises:
            ModelException: Si el archivo no existe o falla carga
        """
        # Retornar si ya está cacheado
        if model_name in self._models:
            logger.debug(f"Modelo cacheado: {model_name}")
            return self._models[model_name]
        
        filepath = os.path.join(self.models_dir, model_name)
        
        if not filepath.endswith('.cbm'):
            filepath += '.cbm'
        
        if not os.path.exists(filepath):
            raise ModelException(
                f"Archivo modelo no encontrado: {filepath}"
            )
        
        try:
            from catboost import CatBoostClassifier
            
            logger.info(f"Cargando modelo CatBoost: {model_name}")
            model = CatBoostClassifier()
            model.load_model(filepath)
            
            # Cachear para futuros usos
            self._models[model_name] = model
            
            logger.info(f"Modelo CatBoost cargado exitosamente: {model_name}")
            
            return model
        
        except ImportError:
            raise ModelException(
                "CatBoost no está instalado. Ejecute: pip install catboost"
            )
        except Exception as e:
            raise ModelException(
                f"Error cargando modelo CatBoost {model_name}: {str(e)}"
            )
    
    def unload_model(self, model_name: str) -> bool:
        """
        Descargar modelo de memoria.
        
        Args:
            model_name: Nombre del modelo a descargar
        
        Returns:
            True si se descaró, False si no existía
        """
        if model_name in self._models:
            del self._models[model_name]
            logger.debug(f"Modelo descargado: {model_name}")
            return True
        return False
    
    def predict_1x2(self, match_features: dict) -> tuple[float, float, float]:
        """
        Usar modelo de clasificación para predecir 1X2.
        
        Args:
            match_features: Features del partido
        
        Returns:
            Tupla (prob_local, prob_empate, prob_visitante)
        
        Raises:
            ModelException: Si hay error en predicción
        """
        try:
            model = self.load_pkl_model('modelo_clasificacion_1x2')
            
            # Asumir que el modelo espera array de features
            # Adaptarse según estructura real del modelo
            import numpy as np
            
            features_array = np.array([list(match_features.values())])
            probabilities = model.predict_proba(features_array)[0]
            
            return tuple(probabilities)
        
        except Exception as e:
            raise ModelException(f"Error en predicción 1X2: {str(e)}")
    
    def get_cached_models(self) -> list[str]:
        """
        Obtener lista de modelos actualmente cacheados.
        
        Returns:
            Lista de nombres de modelos
        """
        return list(self._models.keys())
