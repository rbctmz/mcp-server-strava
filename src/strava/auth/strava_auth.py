import os
import time
import logging
import requests
from datetime import datetime
from typing import Optional

from .rate_limiter import RateLimiter
logger = logging.getLogger(__name__)

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/token"

class StravaAuth:
    def __init__(self):
        self.client_id = os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        self.access_token = os.getenv("STRAVA_ACCESS_TOKEN")
        self.token_expires_at = float(os.getenv("STRAVA_TOKEN_EXPIRES_AT", "0"))
        self._cached_token: Optional[str] = None
        self._last_refresh: Optional[float] = None
        self.rate_limiter = RateLimiter()

    

    def get_access_token(self) -> str:
        """Получение актуального токена с проверкой срока действия"""
        now = datetime.now().timestamp()
        if not self._cached_token or now >= self.token_expires_at - 300:  # 5 минут запас
            return self.refresh_access_token()
        return self._cached_token

    def make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Выполнение запроса с учетом rate limiting"""
        if not url.startswith("https://"):
            url = f"{STRAVA_API_BASE}{url}"
            
        if not self.rate_limiter.can_make_request():
            wait_time = 60  # ждем минуту при достижении лимита
            logging.warning(f"Rate limit reached, waiting {wait_time} seconds")
            time.sleep(wait_time)

        try:
            response = requests.request(method, url, **kwargs)
            self.rate_limiter.add_request()
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            _handle_strava_error(e)

    def refresh_access_token(self) -> str:
        """Обновление токена доступа"""
        try:
            logger.debug(f"Отправка запроса на обновление токена. Client ID: {self.client_id}")
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
            logger.debug("Получен ответ от Strava API")
            
            # Проверяем наличие необходимых полей
            if "access_token" not in data:
                raise ValueError("Отсутствует access_token в ответе")
                
            # Обновляем токены
            self.access_token = data["access_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            self.token_expires_at = data["expires_at"]
            self._cached_token = self.access_token
            self._last_refresh = datetime.now().timestamp()
            
            logger.info("Токены успешно обновлены")
            return self._cached_token
            
        except Exception as e:
            logger.error(f"Ошибка обновления токена: {e}")
            logger.debug(f"Client ID: {self.client_id}, Refresh Token: {self.refresh_token[:10]}...")
            raise