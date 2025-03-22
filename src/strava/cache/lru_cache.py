from functools import lru_cache
from typing import Dict, Any, Optional
import time
import logging

logger = logging.getLogger(__name__)

class StravaCache:
    """LRU-кэш для запросов к Strava API"""
    
    def __init__(self, ttl: int = 300):  # TTL по умолчанию 5 минут
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        logger.info(f"Инициализирован кэш с TTL {ttl} секунд")
    
    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша с логированием"""
        if key in self._cache:
            item = self._cache[key]
            if time.time() - item["timestamp"] < self.ttl:
                logger.debug(f"Cache HIT: {key}")
                return item["value"]
            logger.debug(f"Cache EXPIRED: {key}")
            del self._cache[key]
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Сохранение значения в кэш с логированием"""
        self._cache[key] = {
            "value": value,
            "timestamp": time.time()
        }
        logger.debug(f"Cache SET: {key}")