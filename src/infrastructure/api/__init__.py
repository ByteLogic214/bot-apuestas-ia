"""API infrastructure: HTTP client, API wrappers, and resilience patterns."""

from src.infrastructure.api.base import HTTPClient, HTTPResponse
from src.infrastructure.api.odds_api import OddsAPIClient
from src.infrastructure.api.football_api import FootballAPIClient
from src.infrastructure.api.gemini_api import GeminiAPIClient
from src.infrastructure.api.telegram_api import TelegramAPIClient

__all__ = [
    'HTTPClient',
    'HTTPResponse',
    'OddsAPIClient',
    'FootballAPIClient',
    'GeminiAPIClient',
    'TelegramAPIClient',
]
