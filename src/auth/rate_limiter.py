from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Ограничитель частоты запросов к API"""
    
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.requests = []
    
    def can_make_request(self) -> bool:
        """Проверка возможности сделать запрос"""
        now = datetime.now()
        self.requests = [t for t in self.requests if now - t < timedelta(minutes=1)]
        return len(self.requests) < self.requests_per_minute
    
    def add_request(self):
        """Регистрация нового запроса"""
        self.requests.append(datetime.now())