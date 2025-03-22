import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Union

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from strava.cache import StravaCache
from strava.auth import StravaAuth, RateLimiter

# Настройка логирования
logger = logging.getLogger(__name__)

class StravaApiError(Exception):
    """Ошибки Strava API"""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__(message)

def _handle_strava_error(e: requests.exceptions.RequestException) -> None:
    """Обработка ошибок Strava API"""
    if e.response is not None:
        status_code = e.response.status_code
        if status_code == 401:
            raise StravaApiError("Ошибка авторизации. Проверьте токены.", status_code)
        elif status_code == 429:
            raise StravaApiError("Превышен лимит запросов.", status_code)
        else:
            raise StravaApiError(f"Ошибка Strava API: {e}", status_code)
    raise StravaApiError(f"Сетевая ошибка: {e}")

# Создаем директорию для логов если её нет
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # исправлено с levellevelname на levelname
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "strava_api.log")),
    ],
)

# Создаем кэш после инициализации логирования
strava_cache = StravaCache(ttl=300)  # 5 минут
logger.info("Инициализирован кэш Strava API")

# Загружаем конфигурацию
load_dotenv()

# Создаем MCP сервер
mcp = FastMCP("Strava Integration")

# Создаем экземпляр авторизации
strava_auth = StravaAuth()

# Проверяем токены при старте
try:
    strava_auth.get_access_token()
except Exception as e:
    logger.error(f"Ошибка при проверке токенов: {e}")

@mcp.resource("strava://activities")
def get_recent_activities() -> List[Dict]:
    """Получить активности из Strava API за последние 30 дней"""
    try:
        # Вычисляем дату 30 дней назад
        before = int(time.time())
        after = before - 30 * 24 * 60 * 60

        params = {"before": before, "after": after, "page": 1, "per_page": 200}

        cache_key = f"activities_{hash(frozenset(params.items()))}"
        cached = strava_cache.get(cache_key)
        if cached:
            return cached

        access_token = strava_auth.get_access_token()
        response = strava_auth.make_request(
            "GET",
            "/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params
        )

        activities = response.json()
        strava_cache.set(cache_key, activities)
        logger.info(f"Получено активностей: {len(activities)}")
        return activities

    except Exception as e:
        logger.error(f"Ошибка API Strava: {e}")
        raise RuntimeError(f"Ошибка получения активностей: {e}") from e

@mcp.resource("strava://activities/{before}/{after}/{page}/{per_page}")
def get_recent_activities_with_pagination(before: Optional[int] = None, after: Optional[int] = None, page: int = 1, per_page: int = 30) -> List[Dict]:
    """Получить активности из Strava API с поддержкой пагинации и фильтрации"""
    try:
        params = {"page": page, "per_page": min(per_page, 200)}
        if before:
            params["before"] = before
        if after:
            params["after"] = after

        cache_key = f"activities_{hash(frozenset(params.items()))}"
        cached = strava_cache.get(cache_key)
        if cached:
            return cached

        access_token = strava_auth.get_access_token()
        response = strava_auth.make_request(
            "GET",
            "/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params
        )

        activities = response.json()
        strava_cache.set(cache_key, activities)
        logger.info(f"Получено активностей: {len(activities)}")
        return activities

    except Exception as e:
        logger.error(f"Ошибка API Strava: {e}")
        raise RuntimeError(f"Ошибка получения активностей: {e}") from e


@mcp.resource("strava://activities/{activity_id}")
def get_activity(activity_id: str) -> dict:
    """Получить детали конкретной активности"""
    cache_key = f"activity_{activity_id}"
    
    # Проверяем кэш
    cached = strava_cache.get(cache_key)
    if cached:
        logger.debug(f"Возвращаем активность {activity_id} из кэша")
        return cached
    
    try:
        access_token = strava_auth.get_access_token()
        response = strava_auth.make_request(
            "GET",
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        activity = response.json()
        
        # Сохраняем в кэш
        strava_cache.set(cache_key, activity)
        logger.info(f"Получена и закэширована активность {activity_id}: {activity.get('type')}")
        
        return activity

    except Exception as e:
        logger.error(f"Ошибка получения активности {activity_id}: {e}")
        raise RuntimeError("Не удалось получить активность") from e

@mcp.resource("strava://athlete/zones")
def get_athlete_zones() -> Dict:
    """Получить тренировочные зоны атлета
    
    Returns:
        Dict: Словарь с зонами для каждого типа (пульс, мощность, темп)
        
    Raises:
        RuntimeError: При ошибке получения зон
    """
    cache_key = "athlete_zones"
    # Проверяем кэш
    cached = strava_cache.get(cache_key)
    if cached:
        logger.debug("Возвращаем зоны из кэша")
        return cached

    try:
        access_token = strava_auth.get_access_token()
        logger.debug(f"Запрос зон с токеном: {access_token[:10]}...")
        
        response = strava_auth.make_request(
            "GET",
            "/athlete/zones",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        
        zones = response.json()
        result = {
            "heart_rate": zones.get("heart_rate", {"custom_zones": False, "zones": []}),
            "power": zones.get("power", {"custom_zones": False, "zones": []}),
            "pace": zones.get("pace", {"custom_zones": False, "zones": []}),
        }
        
        # Сохраняем в кэш
        strava_cache.set(cache_key, result)
        logger.debug(f"Получены и закэшированы типы зон: {list(zones.keys())}")
        
        return result

    except Exception as e:
        logger.error(f"Ошибка получения зон: {e}")
        raise RuntimeError("Не удалось получить тренировочные зоны") from e

def _get_zone_name(index: int) -> str:
    """Получить название зоны по индексу"""
    zone_names = {
        0: "Recovery",     # Восстановление
        1: "Endurance",    # Выносливость
        2: "Tempo",        # Темповая
        3: "Threshold",    # Пороговая
        4: "Anaerobic"     # Анаэробная
    }
    return zone_names.get(index, "Unknown")

@mcp.resource("strava:///athlete/clubs")
def get_athlete_stats() -> Dict:
    """Получить клубы атлета

    Returns:
        Dict: Клубы атлета
    """
    cache_key = "athlete_clubs"
    
    # Проверяем кэш
    cached = strava_cache.get(cache_key)
    if cached:
        logger.debug("Возвращаем клубы из кэша")
        return cached

    try:
        access_token = strava_auth.get_access_token()
        response = strava_auth.make_request(
            "GET",
            "https://www.strava.com/api/v3/athlete/clubs",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        clubs = response.json()
        logger.info(f"Получены клубы атлета: {len(clubs)}")
        # Сохраняем в кэш
        strava_cache.set(cache_key, clubs)
        logger.info(f"Получено и закэшировано клубов: {len(clubs)}")
        
        return clubs
    except Exception as e:
        logger.error(f"Ошибка получения клубов: {e}")
        raise RuntimeError("Не удалось получить клубы атлета") from e        

@mcp.resource("strava://gear/{gear_id}")
def get_gear(gear_id: str) -> Dict:
    """Получить информацию о снаряжении

    Args:
        gear_id: ID снаряжения
    Returns:
        Dict: Информация о снаряжении
    """
    cache_key = f"gear_{gear_id}"
    
    # Проверяем кэш
    cached = strava_cache.get(cache_key)
    if cached:
        logger.debug(f"Возвращаем снаряжение {gear_id} из кэша")
        return cached

    try:
        access_token = strava_auth.get_access_token()
        response = strava_auth.make_request(
            "GET",
            f"https://www.strava.com/api/v3/gear/{gear_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        gear = response.json()
        logger.info(f"Получено снаряжение {gear_id}: {gear.get('name')}")
        # Сохраняем в кэш
        strava_cache.set(cache_key, gear)
        logger.info(f"Получено и закэшировано снаряжение {gear_id}: {gear.get('name')}")
        return gear
    except Exception as e:
        logger.error(f"Ошибка получения снаряжения {gear_id}: {e}")
        raise RuntimeError("Не удалось получить снаряжение") from e

@mcp.tool()
def get_activity_by_id(activity_id: Union[str, int]) -> dict:
    """Получить активность из Strava API по ID
    Args:
        activity_id: ID активности (строка или число)
    Returns:
        dict: Активность
    """
    # Преобразуем activity_id в строку
    activity_id = str(activity_id)

    try:
       activity = get_activity(activity_id)
       return activity
    except Exception as e:
        logger.error(f"Ошибка получения активности {activity_id}: {e}")
        return {"error": f"Не удалось получить активность: {str(e)}"}


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
            "analysis": {"pace": _calculate_pace(activity), "effort": _calculate_effort(activity)},
        }
    except Exception as e:
        logger.error(f"Ошибка анализа активности {activity_id}: {e}")
        return {"error": f"Не удалось проанализировать активность: {str(e)}"}

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
    if "average_heartrate" not in activity:
        return "Неизвестно"

    hr = activity["average_heartrate"]
    if hr < 120:
        return "Легкая"
    if hr < 150:
        return "Средняя"
    return "Высокая"

@mcp.tool()
def analyze_training_load(activities: List[Dict]) -> Dict:
    """Анализ тренировочной нагрузки"""
    summary = {
        "activities_count": len(activities),
        "total_distance": 0,
        "total_time": 0,
        "activities_by_type": {},
        "heart_rate_zones": {
            "easy": 0,  # ЧСС < 120
            "medium": 0,  # ЧСС 120-150
            "hard": 0,  # ЧСС > 150
        },
    }

    for activity in activities:
        activity_type = activity.get("type")

        # Обновляем счетчик типа активности
        if activity_type not in summary["activities_by_type"]:
            summary["activities_by_type"][activity_type] = 0
        summary["activities_by_type"][activity_type] += 1

        # Суммируем дистанцию и время
        summary["total_distance"] += activity.get("distance", 0)
        summary["total_time"] += activity.get("moving_time", 0)

        # Анализируем зоны ЧСС
        hr = activity.get("average_heartrate", 0)
        if hr:
            if hr < 120:
                summary["heart_rate_zones"]["easy"] += 1
            elif hr < 150:
                summary["heart_rate_zones"]["medium"] += 1
            else:
                summary["heart_rate_zones"]["hard"] += 1

    # Конвертируем единицы измерения
    summary["total_distance"] = round(summary["total_distance"] / 1000, 2)  # в километры
    summary["total_time"] = round(summary["total_time"] / 3600, 2)  # в часы

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

    # Форматируем вывод для лучшей читаемости
    result = {
        "analysis": {
            "activities": {
                "total": analysis["activities_count"],
                "distance": f"{analysis['total_distance']:.1f} км",
                "time": f"{analysis['total_time']:.1f} ч",
                "distribution": {
                    activity: {
                        "count": count,
                        "percent": f"{(count / total_activities * 100):.0f}%",
                    }
                    for activity, count in activity_types.items()
                },
            },
            "intensity": {
                "zones": {
                    "easy": f"{easy_percent:.0f}%" if total_zone_activities > 0 else "0%",
                    "medium": f"{medium_percent:.0f}%" if total_zone_activities > 0 else "0%",
                    "hard": f"{hard_percent:.0f}%" if total_zone_activities > 0 else "0%",
                },
                "status": "Сбалансировано" if 60 <= easy_percent <= 80 else "Требует корректировки",
            },
        },
        "recommendations": [
            {"category": recommendation.split("\n")[0], "details": recommendation.split("\n")[1:]}
            for recommendation in recommendations
        ],
        "summary": {
            "status": "✅ Тренировки сбалансированы"
            if not recommendations
            else "⚠️ Есть рекомендации",
            "weekly": {
                "activities": total_activities,
                "distance": f"{weekly_distance:.1f} км",
                "time": f"{weekly_hours:.1f} ч",
            },
        },
    }

    return result
