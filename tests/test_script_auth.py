import logging
import os

import pytest

# Import main from OAuth script
import scripts.auth as auth_script


def test_main_no_env(monkeypatch, caplog):
    """Если переменные STRAVA_CLIENT_ID или STRAVA_CLIENT_SECRET не заданы, main() логирует ошибку"""
    # Ensure env vars are not set
    monkeypatch.delenv('STRAVA_CLIENT_ID', raising=False)
    monkeypatch.delenv('STRAVA_CLIENT_SECRET', raising=False)
    caplog.set_level(logging.ERROR)

    result = auth_script.main()
    # main returns None on error
    assert result is None
    # Check error logged
    assert 'STRAVA_CLIENT_ID или STRAVA_CLIENT_SECRET' in caplog.text
    
def test_auth_handler_do_get_success(monkeypatch, tmp_path):
    """Тест успешного OAuth-обработчика AuthHandler.do_GET"""
    # Prepare environment variables
    monkeypatch.setenv('STRAVA_CLIENT_ID', 'cid')
    monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'csecret')
    # Prepare mock response for requests.post
    from scripts.auth import AuthHandler, SUCCESS_HTML, ERROR_HTML
    class MockResp:
        def raise_for_status(self): pass
        def json(self): return {'access_token': 'tok', 'refresh_token': 'rtok', 'expires_at': 12345}
    monkeypatch.setattr('scripts.auth.requests.post', lambda *args, **kwargs: MockResp())
    # Capture set_key calls
    set_calls = []
    monkeypatch.setattr('scripts.auth.set_key', lambda env, key, val: set_calls.append((key, val)))
    # Instantiate handler without full TCP machinery
    from io import BytesIO
    handler = AuthHandler.__new__(AuthHandler)
    handler.path = '/?code=abc123'
    handler.send_response = lambda code: setattr(handler, 'status', code)
    handler.send_header = lambda k, v: None
    handler.end_headers = lambda: None
    handler.wfile = BytesIO()
    # Call do_GET
    handler.do_GET()
    output = handler.wfile.getvalue().decode('utf-8')
    assert 'Авторизация успешна' in output
    # Verify tokens saved
    assert ('STRAVA_ACCESS_TOKEN', 'tok') in set_calls
    assert ('STRAVA_REFRESH_TOKEN', 'rtok') in set_calls
    assert ('STRAVA_TOKEN_EXPIRES_AT', '12345') in set_calls

def test_auth_handler_do_get_error(monkeypatch):
    """Тест обработки ошибок в AuthHandler.do_GET при отсутствии кода"""
    from scripts.auth import AuthHandler, ERROR_HTML
    # No code in path
    handler = AuthHandler.__new__(AuthHandler)
    handler.path = '/?no_code=1'
    handler.send_response = lambda code: setattr(handler, 'status', code)
    handler.send_header = lambda k, v: None
    handler.end_headers = lambda: None
    from io import BytesIO
    handler.wfile = BytesIO()
    # Call do_GET
    handler.do_GET()
    output = handler.wfile.getvalue().decode('utf-8')
    assert 'Ошибка авторизации' in output