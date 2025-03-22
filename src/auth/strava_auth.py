from datetime import datetime
import os
import logging
from typing import Optional
import requests
from dotenv import load_dotenv
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class StravaAuth:
    """Аутентификация в Strava API"""
    
    def __init__(self):
        load_dotenv()
        
        self.client_id = int(os.getenv("STRAVA_CLIENT_ID", "0"))  # Преобразуем в int
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        self.access_token = os.getenv("STRAVA_ACCESS_TOKEN")
        self.token_expires_at = int(os.getenv("STRAVA_TOKEN_EXPIRES_AT", "0"))
        
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError("Не заданы необходимые переменные окружения")
            
        self._cached_token: Optional[str] = None
        self._last_refresh: float = 0
        self.rate_limiter = RateLimiter()
        
        # Сразу проверяем токены при инициализации
        self.get_access_token()
    
    def refresh_access_token(self) -> str:
        """Обновление токена доступа"""
        try:
            logger.debug(
                f"Отправка запроса на обновление токена. "
                f"Client ID: {self.client_id}, "
                f"Refresh token exists: {bool(self.refresh_token)}"
            )
            
            if not self.client_id or not self.client_secret or not self.refresh_token:
                raise ValueError(
                    f"Отсутствуют необходимые данные для обновления токена. "
                    f"ID: {bool(self.client_id)}, "
                    f"Secret: {bool(self.client_secret)}, "
                    f"Refresh: {bool(self.refresh_token)}"
                )

            response = self.make_request(
                "POST",
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            
            data = response.json()
            logger.debug(f"Получен ответ от Strava API: {data.keys()}")
            
            if "access_token" not in data:
                raise ValueError(f"Отсутствует access_token в ответе. Получены поля: {data.keys()}")
                
            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            self.token_expires_at = data["expires_at"]
            self._cached_token = self.access_token
            self._last_refresh = datetime.now().timestamp()
            
            logger.info("Токены успешно обновлены")
            return self._cached_token
            
        except Exception as e:
            logger.error(f"Ошибка обновления токена: {str(e)}")
            raise