import time
from typing import List
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Класс для ограничения запросов к API"""
    def __init__(self):
        self.requests_15min: List[float] = []
        self.requests_daily: List[float] = []
        self.limit_15min = 100
        self.limit_daily = 1000

    def can_make_request(self) -> bool:
        """Проверка возможности сделать запрос"""
        now = time.time()

        # Очистка старых запросов
        self.requests_15min = [t for t in self.requests_15min if now - t < 900]  # 15 минут
        self.requests_daily = [t for t in self.requests_daily if now - t < 86400]  # 24 часа

        return (
            len(self.requests_15min) < self.limit_15min
            and len(self.requests_daily) < self.limit_daily
        )

    def add_request(self):
        """Регистрация нового запроса"""
        now = time.time()
        self.requests_15min.append(now)
        self.requests_daily.append(now)
