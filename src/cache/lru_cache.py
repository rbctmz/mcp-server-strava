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
    
    @lru_cache(maxsize=100)
    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        if key in self._cache:
            item = self._cache[key]
            if time.time() - item["timestamp"] < self.ttl:
                logger.debug(f"Cache hit: {key}")
                return item["value"]
            del self._cache[key]
            logger.debug(f"Cache expired: {key}")
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Сохранение значения в кэш"""
        self._cache[key] = {
            "value": value,
            "timestamp": time.time()
        }
        logger.debug(f"Cache set: {key}")
        
    def clear(self) -> None:
        """Очистка кэша"""
        self._cache.clear()
        self.get.cache_clear()
        logger.info("Cache cleared")