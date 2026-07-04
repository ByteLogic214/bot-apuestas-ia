"""
Cliente HTTP base con manejo de reintentos y timeouts.
Implementa patrón de reintento exponencial para resiliencia.
"""

import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.core.config import get_config
from src.core.exceptions import RetryableException, APIException

logger = logging.getLogger(__name__)


@dataclass
class HTTPResponse:
    """Respuesta estandarizada de API."""
    status_code: int
    data: Any
    headers: Dict[str, str]
    elapsed_ms: float
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Verificar si la respuesta fue exitosa."""
        return 200 <= self.status_code < 300


class HTTPClient:
    """
    Cliente HTTP robusto con reintentos automáticos.
    Características:
    - Timeout configurable
    - Reintentos exponenciales
    - Pool de conexiones reutilizables
    - Logging detallado
    """
    
    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3):
        """
        Inicializar cliente HTTP.
        
        Args:
            base_url: URL base para todas las solicitudes
            timeout: Timeout en segundos
            max_retries: Número máximo de reintentos
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()
        self.logger = logger
    
    def _create_session(self) -> requests.Session:
        """Crear sesión con reintentos configurados."""
        session = requests.Session()
        
        # Configurar estrategia de reintentos
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,  # 1s, 2s, 4s, 8s...
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    @retry(
        retry=retry_if_exception_type(RetryableException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def get(self, endpoint: str, params: Optional[Dict] = None,
            headers: Optional[Dict] = None) -> HTTPResponse:
        """
        GET request con reintentos automáticos.
        
        Args:
            endpoint: Ruta del endpoint
            params: Parámetros query
            headers: Headers personalizados
        
        Returns:
            HTTPResponse con datos y metadata
        
        Raises:
            APIException: Error en la solicitud
        """
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            self.logger.debug(f"GET {url} con params={params}")
            
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Verificar status code
            if response.status_code == 429:  # Rate limit
                raise RetryableException(
                    f"Rate limit alcanzado. Retry-After: {response.headers.get('Retry-After')}"
                )
            
            if response.status_code >= 500:  # Server error
                raise RetryableException(
                    f"Error de servidor: {response.status_code}"
                )
            
            response.raise_for_status()
            
            data = response.json()
            
            self.logger.info(
                f"GET {endpoint} exitoso ({elapsed_ms:.1f}ms, "
                f"status={response.status_code})"
            )
            
            return HTTPResponse(
                status_code=response.status_code,
                data=data,
                headers=dict(response.headers),
                elapsed_ms=elapsed_ms
            )
        
        except requests.exceptions.Timeout as e:
            raise RetryableException(f"Timeout después de {self.timeout}s: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            raise RetryableException(f"Error de conexión: {str(e)}")
        except requests.exceptions.HTTPError as e:
            raise APIException(f"HTTP Error {response.status_code}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error inesperado en GET: {str(e)}")
            raise APIException(f"Error en solicitud: {str(e)}")
    
    @retry(
        retry=retry_if_exception_type(RetryableException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def post(self, endpoint: str, json_data: Optional[Dict] = None,
             headers: Optional[Dict] = None) -> HTTPResponse:
        """
        POST request con reintentos automáticos.
        
        Args:
            endpoint: Ruta del endpoint
            json_data: Datos a enviar
            headers: Headers personalizados
        
        Returns:
            HTTPResponse con datos y metadata
        
        Raises:
            APIException: Error en la solicitud
        """
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            self.logger.debug(f"POST {url} con data={json_data}")
            
            response = self.session.post(
                url,
                json=json_data,
                headers=headers,
                timeout=self.timeout
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 429:
                raise RetryableException(
                    f"Rate limit alcanzado. Retry-After: {response.headers.get('Retry-After')}"
                )
            
            if response.status_code >= 500:
                raise RetryableException(f"Error de servidor: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json() if response.text else {}
            
            self.logger.info(
                f"POST {endpoint} exitoso ({elapsed_ms:.1f}ms, "
                f"status={response.status_code})"
            )
            
            return HTTPResponse(
                status_code=response.status_code,
                data=data,
                headers=dict(response.headers),
                elapsed_ms=elapsed_ms
            )
        
        except requests.exceptions.Timeout as e:
            raise RetryableException(f"Timeout después de {self.timeout}s: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            raise RetryableException(f"Error de conexión: {str(e)}")
        except requests.exceptions.HTTPError as e:
            raise APIException(f"HTTP Error {response.status_code}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error inesperado en POST: {str(e)}")
            raise APIException(f"Error en solicitud: {str(e)}")
    
    def close(self):
        """Cerrar sesión y liberar recursos."""
        self.session.close()
        self.logger.debug("Sesión HTTP cerrada")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
