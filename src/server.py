from mcp.server.fastmcp import FastMCP
import os
from dotenv import load_dotenv
import requests
from datetime import datetime
import logging
import sys
from typing import Optional, Dict, List, Union
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

class RateLimiter:
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
        
        return len(self.requests_15min) < self.limit_15min and len(self.requests_daily) < self.limit_daily

    def add_request(self):
        """Регистрация нового запроса"""
        now = time.time()
        self.requests_15min.append(now)
        self.requests_daily.append(now)

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
            logging.error(f"Request error: {e}")
            raise RuntimeError(f"API request failed: {e}")

    def refresh_access_token(self) -> str:
        """Обновление токена доступа"""
        try:
            response = self.make_request(
                "POST",
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            self.token_expires_at = data["expires_at"]
            self._cached_token = self.access_token
            self._last_refresh = datetime.now().timestamp()
            return self._cached_token
        except Exception as e:
            logger.error(f"Ошибка обновления токена: {e}")
            raise

# Создаем директорию для логов если её нет
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, 'strava_api.log'))
    ]
)
logger = logging.getLogger(__name__)

# Загружаем конфигурацию
load_dotenv()

# Создаем MCP сервер
mcp = FastMCP("Strava Integration")

# Создаем экземпляр авторизации
strava_auth = StravaAuth()

@mcp.resource("strava://activities")
def get_recent_activities() -> List[Dict]:
    """Получить последние активности из Strava"""
    limit = 10  # Default value moved into function
    logger.info(f"Запрашиваем последние {limit} активностей")
    try:
        access_token = strava_auth.get_access_token()
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"per_page": limit}
        )
        response.raise_for_status()
        activities = response.json()
        logger.info(f"Получено {len(activities)} активностей")
        return activities
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка API Strava: {e}")
        raise RuntimeError(f"Ошибка получения активностей: {e}")

@mcp.resource("strava://activities/{activity_id}")
def get_activity(activity_id: str) -> dict:
    """Получить детали конкретной активности"""
    response = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}",
        headers={"Authorization": f"Bearer {os.getenv('STRAVA_ACCESS_TOKEN')}"}
    )
    return response.json()

@mcp.tool()
def analyze_activity(activity_id: Union[str, int]) -> dict:
    """Анализ активности из Strava
    
    Args:
        activity_id: ID активности (строка или число)
    Returns:
        dict: Результаты анализа активности
    """
    # Преобразуем activity_id в строку
    activity_id = str(activity_id)
    
    try:
        activity = get_activity(activity_id)
        return {
            "type": activity.get("type"),
            "distance": activity.get("distance"),
            "moving_time": activity.get("moving_time"),
            "analysis": {
                "pace": _calculate_pace(activity),
                "effort": _calculate_effort(activity)
            }
        }
    except Exception as e:
        logger.error(f"Ошибка анализа активности {activity_id}: {e}")
        return {
            "error": f"Не удалось проанализировать активность: {str(e)}"
        }

def _calculate_pace(activity: dict) -> float:
    """Расчет темпа активности"""
    try:
        if activity.get("type") == "Run":
            # Для бега: мин/км
            return (activity.get("moving_time", 0) / 60) / (activity.get("distance", 0) / 1000)
        elif activity.get("type") == "Ride":
            # Для велосипеда: км/ч
            return (activity.get("distance", 0) / 1000) / (activity.get("moving_time", 0) / 3600)
        return 0
    except (TypeError, ZeroDivisionError):
        return 0

def _calculate_effort(activity: dict) -> str:
    """Оценка нагрузки"""
    if "average_heartrate" in activity:
        hr = activity["average_heartrate"]
        if hr < 120: return "Легкая"
        elif hr < 150: return "Средняя"
        else: return "Высокая"
    return "Неизвестно"

@mcp.tool()
def analyze_training_load(activities: List[Dict]) -> Dict:
    """Анализ тренировочной нагрузки"""
    summary = {
        "activities_count": len(activities),
        "total_distance": 0,
        "total_time": 0,
        "activities_by_type": {},
        "heart_rate_zones": {
            "easy": 0,    # ЧСС < 120
            "medium": 0,  # ЧСС 120-150
            "hard": 0     # ЧСС > 150
        }
    }
    
    for activity in activities:
        # Подсчет по типам активностей
        activity_type = activity.get("type")
        if activity_type not in summary["activities_by_type"]:
            summary["activities_by_type"][activity_type] = 0
        summary["activities_by_type"][activity_type] += 1
        
        # Общая дистанция и время
        summary["total_distance"] += activity.get("distance", 0)
        summary["total_time"] += activity.get("moving_time", 0)
        
        # Анализ зон ЧСС
        hr = activity.get("average_heartrate", 0)
        if hr:
            if hr < 120:
                summary["heart_rate_zones"]["easy"] += 1
            elif hr < 150:
                summary["heart_rate_zones"]["medium"] += 1
            else:
                summary["heart_rate_zones"]["hard"] += 1

    # Конвертируем метры в километры
    summary["total_distance"] = round(summary["total_distance"] / 1000, 2)
    # Конвертируем секунды в часы
    summary["total_time"] = round(summary["total_time"] / 3600, 2)

    return summary

@mcp.tool()
def get_activity_recommendations() -> Dict:
    """Получить рекомендации по тренировкам на основе анализа последних активностей"""
    activities = get_recent_activities()
    analysis = analyze_training_load(activities)
    
    recommendations = []
    
    # Анализ разнообразия тренировок
    activity_types = analysis["activities_by_type"]
    total_activities = analysis["activities_count"]
    
    # Анализ интенсивности по зонам
    zones = analysis["heart_rate_zones"]
    total_zone_activities = sum(zones.values())
    if total_zone_activities > 0:
        easy_percent = (zones["easy"] / total_zone_activities) * 100
        medium_percent = (zones["medium"] / total_zone_activities) * 100
        hard_percent = (zones["hard"] / total_zone_activities) * 100
        
        # Проверка распределения интенсивности
        if easy_percent < 70:
            recommendations.append(
                f"Слишком мало легких тренировок ({easy_percent:.0f}%). "
                "Рекомендуется:\n"
                "- Добавить восстановительные тренировки\n"
                "- Больше базовых тренировок в низких пульсовых зонах\n"
                "- Использовать контроль пульса во время тренировок"
            )
        
        if medium_percent > 40:
            recommendations.append(
                f"Большой процент тренировок в средней зоне ({medium_percent:.0f}%). "
                "Рекомендуется:\n"
                "- Четко разделять легкие и интенсивные тренировки\n"
                "- Избегать тренировок в 'серой зоне'"
            )
    
    # Анализ объемов по видам спорта
    if "Run" in activity_types:
        run_volume = sum(a.get("distance", 0) for a in activities if a.get("type") == "Run") / 1000
        if run_volume < 20:
            recommendations.append(
                f"Беговой объем ({run_volume:.1f} км) ниже оптимального.\n"
                "Рекомендации по увеличению:\n"
                "- Добавить 1-2 км к длинной пробежке еженедельно\n"
                "- Включить легкие восстановительные пробежки\n"
                "- Постепенно довести объем до 30-40 км в неделю"
            )
    
    # Анализ общего объема
    weekly_distance = analysis["total_distance"]
    weekly_hours = analysis["total_time"]
    
    if weekly_hours < 5:
        recommendations.append(
            f"Общий объем ({weekly_hours:.1f} ч) можно увеличить.\n"
            "Рекомендации:\n"
            "- Постепенно добавлять по 30 минут в неделю\n"
            "- Включить кросс-тренировки для разнообразия\n"
            "- Следить за самочувствием при увеличении нагрузок"
        )
    
    # Рекомендации по восстановлению
    if total_zone_activities > 5:
        recommendations.append(
            "Рекомендации по восстановлению:\n"
            "- Обеспечить 7-8 часов сна\n"
            "- Планировать легкие дни после интенсивных тренировок\n"
            "- Следить за питанием и гидратацией"
        )
    
    # Если всё сбалансировано
    if not recommendations:
        recommendations.append(
            "Тренировки хорошо сбалансированы!\n"
            "Рекомендации по поддержанию формы:\n"
            "- Продолжать текущий план тренировок\n"
            "- Вести дневник тренировок\n"
            "- Регулярно анализировать прогресс"
        )
    
    return {
        "analysis": analysis,
        "recommendations": recommendations,
        "summary": {
            "weekly_stats": {
                "distance": f"{weekly_distance:.1f} км",
                "time": f"{weekly_hours:.1f} ч",
                "activities": total_activities
            },
            "intensity_distribution": {
                "easy": f"{easy_percent:.0f}%" if total_zone_activities > 0 else "0%",
                "medium": f"{medium_percent:.0f}%" if total_zone_activities > 0 else "0%",
                "hard": f"{hard_percent:.0f}%" if total_zone_activities > 0 else "0%"
            },
            "activity_distribution": {
                activity: f"{(count/total_activities*100):.0f}%"
                for activity, count in activity_types.items()
            }
        }
    }