import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests

from src.server import (
    StravaAuth,
    analyze_activity,
    analyze_training_load,
    get_recent_activities,
)


@pytest.fixture
def mock_env_vars():
    """Фикстура с тестовыми переменными окружения"""
    return {
        "STRAVA_CLIENT_ID": "test_id",
        "STRAVA_CLIENT_SECRET": "test_secret",
        "STRAVA_REFRESH_TOKEN": "test_refresh",
        "STRAVA_ACCESS_TOKEN": "test_access",
        "STRAVA_TOKEN_EXPIRES_AT": "1740871740",
    }


@pytest.fixture
def mock_activity():
    """Фикстура с тестовой активностью"""
    return {
        "id": "test_activity",
        "type": "Run",
        "distance": 5000,
        "moving_time": 1800,
        "average_heartrate": 140,
    }


@pytest.fixture
def mock_activities():
    """Фикстура со списком тестовых активностей"""
    return [
        {"type": "Run", "distance": 5000, "moving_time": 1800, "average_heartrate": 140},
        {"type": "Swim", "distance": 2000, "moving_time": 3600, "average_heartrate": 110},
    ]


@pytest.fixture
def strava_auth(mock_env_vars):
    """Фикстура для создания StravaAuth с тестовыми переменными"""
    with patch.dict(os.environ, mock_env_vars):
        return StravaAuth()


def test_strava_auth_initialization(mock_env_vars):
    """Тест инициализации StravaAuth"""
    with patch.dict(os.environ, mock_env_vars):
        auth = StravaAuth()
        assert auth.client_id == "test_id"
        assert auth.client_secret == "test_secret"
        assert auth._cached_token is None


def test_get_access_token_refresh(mock_env_vars):
    """Тест обновления токена доступа"""
    with patch.dict(os.environ, mock_env_vars):
        auth = StravaAuth()
        with patch("requests.request") as mock_request:  # Изменено с post на request
            mock_response = Mock()
            mock_response.json.return_value = {  # Правильный формат ответа
                "access_token": "new_token",
                "refresh_token": "new_refresh",
                "expires_at": 1740871740,
            }
            mock_response.raise_for_status = lambda: None
            mock_request.return_value = mock_response

            token = auth.get_access_token()
            assert token == "new_token"
            assert auth._cached_token == "new_token"


def test_refresh_token_success(strava_auth):
    """Тест успешного обновления токена"""
    with patch("requests.request") as mock_request:
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_at": 1740871740,
        }
        mock_response.raise_for_status = lambda: None
        mock_request.return_value = mock_response

        token = strava_auth.refresh_access_token()
        assert token == "new_token"
        assert strava_auth._cached_token == "new_token"


def test_refresh_token_failure(strava_auth):
    """Тест обработки ошибок при обновлении токена"""
    with patch("requests.request") as mock_request:  # Изменено с post на request
        mock_request.side_effect = requests.exceptions.RequestException("Network error")

        with pytest.raises(RuntimeError) as exc_info:
            strava_auth.refresh_access_token()

        assert "Network error" in str(exc_info.value)
        assert strava_auth._cached_token is None


def test_get_access_token_cached(strava_auth):
    """Тест использования кэшированного токена"""
    strava_auth._cached_token = "cached_token"
    strava_auth.token_expires_at = datetime.now().timestamp() + 600

    token = strava_auth.get_access_token()

    assert token == "cached_token"


def test_analyze_activity(mock_activity):
    """Тест анализа активности"""
    with patch("src.server.get_activity") as mock_get:
        mock_get.return_value = {
            "type": "Run",
            "distance": 5000,
            "moving_time": 1800,
            "average_heartrate": 140,
        }
        
        result = analyze_activity("test_id")
        assert result["type"] == "Run"
        assert "pace" in result["analysis"]
        assert result["analysis"]["effort"] == "Средняя"


def test_analyze_training_load(mock_activities):
    """Тест анализа тренировочной нагрузки"""
    result = analyze_training_load(mock_activities)

    assert result["activities_count"] == 2
    assert result["total_distance"] == 7.0  # (5000 + 2000) / 1000
    assert result["total_time"] == 1.5  # (1800 + 3600) / 3600
    assert len(result["activities_by_type"]) == 2
    assert result["activities_by_type"]["Run"] == 1
    assert result["activities_by_type"]["Swim"] == 1
    assert result["heart_rate_zones"]["easy"] == 1
    assert result["heart_rate_zones"]["medium"] == 1


def test_get_recent_activities():
    """Тест получения последних активностей"""
    with patch.object(StravaAuth, "get_access_token") as mock_token:
        mock_token.return_value = "test_token"
        
        with patch("src.server.strava_auth.make_request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = [{"type": "Run"}]
            mock_request.return_value = mock_response

            activities = get_recent_activities()
            assert len(activities) == 1
            assert activities[0]["type"] == "Run"


def test_get_recent_activities_with_limit():
    """Тест получения активностей с лимитом"""
    with patch.object(StravaAuth, "get_access_token") as mock_token:
        mock_token.return_value = "test_token"
        
        with patch("src.server.strava_auth.make_request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = [
                {"id": 1, "type": "Run"},
                {"id": 2, "type": "Ride"},
            ]
            mock_request.return_value = mock_response

            activities = get_recent_activities()
            assert len(activities) == 2
            assert activities[0]["type"] == "Run"
            assert activities[1]["type"] == "Ride"


def test_get_recent_activities_error_handling():
    """Тест обработки ошибок при получении активностей"""
    with patch("src.server.strava_auth.make_request") as mock_request:
        mock_request.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError) as exc_info:
            get_recent_activities()
        assert "API error" in str(exc_info.value)


@pytest.mark.parametrize(
    "activity_id",
    [
        "13743554839",  # строка
        13743554839,  # число
    ],
)
def test_analyze_activity_id_types(activity_id):
    """Тест обработки разных типов activity_id"""
    with patch("src.server.get_activity") as mock_get:
        mock_get.return_value = {
            "type": "Run",
            "distance": 5000,
            "moving_time": 1800,
            "average_heartrate": 140,
        }
        
        result = analyze_activity(activity_id)
        assert result["type"] == "Run"
