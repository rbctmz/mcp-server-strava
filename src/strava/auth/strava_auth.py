import os
import time
import logging
import requests
from datetime import datetime
from typing import Optional

from .rate_limiter import RateLimiter
logger = logging.getLogger(__name__)

def global_handle_strava_error(error: Exception):  # Renamed function
    """Обработка ошибок Strava API на уровне модуля"""
    logger.error(f"Strava API Error: {error}")
    raise RuntimeError(f"Strava API Error: {error}") from error

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/token"

class StravaAuth:
    def __init__(self):
        self.client_id = os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        self.access_token = os.getenv("STRAVA_ACCESS_TOKEN")
        # Timestamp when access token expires
        self.token_expires_at = float(os.getenv("STRAVA_TOKEN_EXPIRES_AT", "0"))
        # In-memory cached token
        self._cached_token: Optional[str] = None
        self._last_refresh: Optional[float] = None
        # Rate limiter for API calls
        self.rate_limiter = RateLimiter()
        # Buffer time (seconds) before actual expiration to refresh token
        self.token_expiry_buffer = 60  # seconds
        # Retry settings for API requests
        self._max_retries = 3
        self._backoff_factor = 1  # base backoff in seconds

    def handle_strava_error(self, error: Exception):
        """Обработка ошибок Strava API"""
        try:
            if isinstance(error, requests.Response):
                status_code = error.status_code
                if status_code == 401:
                    # Avoid recursive call by checking if we're already refreshing
                    if not getattr(self, '_is_refreshing', False):
                        self._is_refreshing = True
                        try:
                            self.refresh_access_token()
                        finally:
                            self._is_refreshing = False
                        return  # Return after successful token refresh
                    raise RuntimeError("Не удалось обновить токен")
                elif status_code == 429:
                    raise RuntimeError("Превышен лимит запросов к API")
                else:
                    raise RuntimeError(f"Ошибка Strava API: {error.text}")
            elif isinstance(error, requests.exceptions.RequestException):
                if error.response is not None:
                    # Instead of recursive call, handle the response directly
                    status_code = error.response.status_code
                    raise RuntimeError(f"HTTP Error {status_code}: {error.response.text}")
                else:
                    raise RuntimeError(f"Сетевая ошибка: {str(error)}")
            else:
                raise RuntimeError(f"Непредвиденная ошибка: {str(error)}")
        except Exception as e:
            logger.error(f"Error handling Strava error: {e}")
            raise

    def get_access_token(self) -> str:
        """Получение актуального токена с проверкой срока действия"""
        now = datetime.now().timestamp()
        # Refresh if no cached token or token is about to expire
        if not self._cached_token or now >= self.token_expires_at - self.token_expiry_buffer:
            return self.refresh_access_token()
        return self._cached_token

    def make_authenticated_request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make an authenticated request to Strava API with proper error handling"""
        access_token = self.get_access_token()
        
        # Ensure we have authorization header
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {access_token}"
        kwargs["headers"] = headers

        # Build full URL if needed
        url = path if path.startswith("https://") else f"{STRAVA_API_BASE}{path}"
        
        try:
            response = requests.request(method, url, **kwargs)
            if not response.ok:
                if response.status_code == 401:
                    # Token expired, refresh and retry once
                    self.refresh_access_token()
                    # Update header with new token
                    headers["Authorization"] = f"Bearer {self._cached_token}"
                    response = requests.request(method, url, **kwargs)
                    if not response.ok:
                        raise RuntimeError(f"Request failed after token refresh: {response.text}")
                else:
                    raise RuntimeError(f"Strava API error: {response.text}")
            return response
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error: {str(e)}")
    
    def make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Выполнение запроса с учетом rate limiting, retry и backoff"""
        for attempt in range(1, self._max_retries + 1):
            # Rate limiting check
            if not self.rate_limiter.can_make_request():
                wait_time = 60
                logger.warning(f"Rate limit reached, waiting {wait_time} seconds")
                time.sleep(wait_time)
            try:
                response = self.make_authenticated_request(method, url, **kwargs)
                self.rate_limiter.add_request()
                return response
            except RuntimeError as e:
                # Retry on transient errors
                if attempt < self._max_retries:
                    backoff = self._backoff_factor * (2 ** (attempt - 1))
                    logger.warning(f"Request attempt {attempt} failed: {e}. Retrying in {backoff} seconds...")
                    time.sleep(backoff)
                    continue
                logger.error(f"All {self._max_retries} request attempts failed: {e}")
                raise

    def refresh_access_token(self) -> str:
        """Обновление токена доступа"""
        try:
            logger.debug(f"Отправка запроса на обновление токена. Client ID: {self.client_id}")
            
            # Делаем прямой запрос без авторизации вместо использования make_request
            # Используем requests.request для возможности патча в тестах
            response = requests.request(
                "POST",
                STRAVA_AUTH_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            
            if not response.ok:
                raise RuntimeError(f"Failed to refresh token: {response.text}")
                
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
            
        except requests.exceptions.RequestException as e:
            # Обработка ошибок сети при обновлении токена
            logger.error(f"Ошибка обновления токена: {e}")
            raise RuntimeError(str(e))
        except Exception as e:
            # Другие ошибки при обновлении токена
            logger.error(f"Ошибка обновления токена: {e}")
            # Маскируем или удаляем вывод refresh token для безопасности
            logger.debug(f"Client ID: {self.client_id}")
            raise