import os
import sys
# Ensure project root is on PYTHONPATH so that 'src' package can be imported when running server script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Union

import requests
import json
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from src.strava.cache import StravaCache
from src.strava.auth import StravaAuth, RateLimiter
from src.strava.errors import handle_strava_error, StravaApiError
import functools

# Настройка логирования
logger = logging.getLogger(__name__)

# Декоратор для обработки ошибок ресурсов MCP
def resource_error_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except StravaApiError:
            raise
        except requests.exceptions.RequestException as e:
            handle_strava_error(e)
        except Exception as e:
            logger.error(f"Ошибка выполнения ресурса {func.__name__}: {e}")
            raise StravaApiError(str(e))
    return wrapper

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
mcp = FastMCP(
    name="Strava Integration",
    version="1.0.0",
    description="Strava API integration for training analysis"
)

# Создаем экземпляр авторизации
strava_auth = StravaAuth()

# Проверяем токены при старте
try:
    strava_auth.get_access_token()
except Exception as e:
    logger.error(f"Ошибка при проверке токенов: {e}")

@resource_error_handler
@mcp.resource("strava://activities")
def get_recent_activities() -> List[Dict]:
    """Получить активности из Strava API за последние 30 дней"""
    try:
        # Вычисляем дату 30 дней назад
        before = int(time.time())
        after = before - 30 * 24 * 60 * 60

        params = {"before": before, "after": after, "page": 1, "per_page": 200}

        # Получение списка активностей без кэша

        access_token = strava_auth.get_access_token()
        response = strava_auth.make_request(
            "GET",
            "/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params
        )

        if not response.ok:
            handle_strava_error(response)
            
        activities = response.json()
        logger.info(f"Получено активностей: {len(activities)}")
        return activities

    except StravaApiError:
        # Пробросим ошибку StravaApiError для внешней обработки
        raise
    except requests.exceptions.RequestException as e:
        handle_strava_error(e)
    except Exception as e:
        logger.error(f"Ошибка API Strava: {e}")
        raise RuntimeError(str(e))

@resource_error_handler
@mcp.resource("strava://activities/{before}/{after}/{page}/{per_page}")
def get_recent_activities_with_pagination(before: Optional[int] = None, after: Optional[int] = None, page: int = 1, per_page: int = 30) -> List[Dict]:
    """Получить активности из Strava API с поддержкой пагинации и фильтрации"""
    try:
        params = {"page": page, "per_page": min(per_page, 200)}
        if before:
            params["before"] = before
        if after:
            params["after"] = after


        access_token = strava_auth.get_access_token()
        response = strava_auth.make_request(
            "GET",
            "/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params
        )

        activities = response.json()
        logger.info(f"Получено активностей: {len(activities)}")
        return activities

    except Exception as e:
        logger.error(f"Ошибка API Strava: {e}")
        raise RuntimeError(f"Ошибка получения активностей: {e}") from e


@resource_error_handler
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
            f"/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        
        activity = response.json()
        
        # Сохраняем в кэш
        strava_cache.set(cache_key, activity)
        logger.info(f"Получена и закэширована активность {activity_id}: {activity.get('type')}")
        
        return activity

    except Exception as e:
        logger.error(f"Ошибка получения активности {activity_id}: {e}")
        if isinstance(e, requests.exceptions.RequestException):
            raise StravaApiError(f"Ошибка API Strava: {str(e)}")
        raise RuntimeError(f"Не удалось получить активность: {str(e)}")

@resource_error_handler
@mcp.resource("strava://athlete/zones")
def get_athlete_zones() -> Dict:
    """Получить тренировочные зоны атлета
    
    Returns:
        Dict: Словарь с зонами для каждого типа (пульс, мощность, темп)
        
    Raises:
        RuntimeError: При ошибке получения зон
    """
    # Получение тренировочных зон без кэша

    try:
        access_token = strava_auth.get_access_token()
        logger.debug("Запрос зон атлета")
        
        response = strava_auth.make_request(
            "GET",
            "/athlete/zones",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        
        zones = response.json()
        # Обогащаем зоны пульса названиями
        raw_hr = zones.get("heart_rate", {"custom_zones": False, "zones": []})
        hr_zones = []
        for idx, z in enumerate(raw_hr.get("zones", [])):
            hr_zones.append({
                "min": z.get("min"),
                "max": z.get("max"),
                "name": f"Z{idx+1} - {_get_zone_name(idx)}"
            })
        raw_hr["zones"] = hr_zones
        # Прочие типы зон
        raw_power = zones.get("power", {"custom_zones": False, "zones": []})
        raw_pace = zones.get("pace", {"custom_zones": False, "zones": []})
        result = {
            "heart_rate": raw_hr,
            "power": raw_power,
            "pace": raw_pace,
        }
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

@resource_error_handler
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

@resource_error_handler
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

@mcp.tool()  # Убираем name параметр
async def get_activity_by_id(activity_id: Union[str, int]) -> Dict:
    """Get activity details from Strava
    
    Args:
        activity_id (Union[str, int]): Activity ID to fetch
        
    Returns:
        Dict: Activity details including type, distance, time and other metrics
    """
    try:
        activity_id = str(activity_id)
        activity = get_activity(activity_id)
        
        return {
            "status": "success",
            "data": activity,
            "metadata": {
                "activity_id": activity_id,
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting activity {activity_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "activity_id": activity_id
        }

@mcp.tool()
def analyze_activity(activity_id: Union[str, int]) -> dict:
    """Анализ активности из Strava

    Args:
        activity_id: ID активности (строка или число)
    Returns:
        dict: Результаты анализа активности
    """
    activity_id = str(activity_id)

    try:
        activity = get_activity(activity_id)
        
        # Calculate pace and zones
        pace = _calculate_pace(activity)
        effort = _calculate_effort(activity)
        
        return {
            "type": activity.get("type"),
            "distance": activity.get("distance"),
            "moving_time": activity.get("moving_time"),
            "average_heartrate": activity.get("average_heartrate"),
            "analysis": {
                "pace": pace,
                "effort": effort,
                "stats": {
                    "elapsed_time": activity.get("elapsed_time"),
                    "elevation_gain": activity.get("total_elevation_gain"),
                    "calories": activity.get("calories"),
                }
            },
        }
    except Exception as e:
        logger.error(f"Ошибка анализа активности {activity_id}: {e}")
        return {
            "error": f"Не удалось проанализировать активность: {str(e)}",
            "activity_id": activity_id
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
    if not activities:
        return {
            "error": "Нет активностей для анализа",
            "activities_count": 0
        }
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
    try:
        # Get recent activities with proper error handling
        try:
            activities = get_recent_activities()
        except StravaApiError as e:
            return {
                "status": "error",
                "error": str(e),
                "recommendations": ["Проверьте подключение к Strava"]
            }

        if not activities:
            return {
                "status": "warning",
                "error": "Нет активностей за последние 30 дней",
                "recommendations": ["Начните записывать тренировки"]
            }

        # Analyze training load
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

    except StravaApiError as e:
        logger.error(f"Ошибка API Strava: {e}")
        return {
            "status": "error",
            "error": str(e),
            "recommendations": ["Проверьте подключение к Strava"]
        }
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")
        return {
            "status": "error",
            "error": "Внутренняя ошибка сервера",
            "details": str(e)
        }

if __name__ == "__main__":
    # Запускаем сервер
    mcp.run()
    logger.info("Сервер запущен")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Сервер остановлен")
        mcp.stop()
        logger.info("Сервер остановлен")
        exit(0)
    except Exception as e:
        logger.error(f"Ошибка сервера: {e}")
        mcp.stop()
        logger.info("Сервер остановлен")
        exit(1)