import pytest
import requests
from requests.models import Response

from src.strava.errors import handle_strava_error, StravaApiError

def make_response(status_code, text="error") -> Response:
    """Создать объект Response с заданным статусом и текстом"""
    resp = Response()
    resp.status_code = status_code
    resp._content = text.encode("utf-8")
    return resp


def test_handle_strava_error_401():
    resp = make_response(401, "unauthorized")
    with pytest.raises(StravaApiError) as exc:
        handle_strava_error(resp)
    assert exc.value.status_code == 401
    assert "Authentication error" in str(exc.value)

def test_handle_strava_error_429():
    resp = make_response(429, "rate limit")
    with pytest.raises(StravaApiError) as exc:
        handle_strava_error(resp)
    assert exc.value.status_code == 429
    assert "Rate limit exceeded" in str(exc.value)

def test_handle_strava_error_other_status():
    resp = make_response(500, text="server error")
    with pytest.raises(StravaApiError) as exc:
        handle_strava_error(resp)
    assert exc.value.status_code == 500
    assert "Strava API error" in str(exc.value)
    assert "server error" in str(exc.value)

def test_handle_strava_error_request_exception_with_response():
    response = make_response(404, text="not found")
    exc = requests.exceptions.RequestException("fail")
    exc.response = response
    with pytest.raises(StravaApiError) as err:
        handle_strava_error(exc)
    assert err.value.status_code == 404

def test_handle_strava_error_request_exception_no_response():
    exc = requests.exceptions.RequestException("network down")
    exc.response = None
    with pytest.raises(StravaApiError) as err:
        handle_strava_error(exc)
    assert "Network error" in str(err.value)

def test_handle_strava_error_unexpected_error():
    with pytest.raises(StravaApiError) as exc:
        handle_strava_error(ValueError("oops"))
    assert "Unexpected error" in str(exc.value)