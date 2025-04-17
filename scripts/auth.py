import logging
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv, set_key

# Настройка логирования
logger = logging.getLogger(__name__)

# Загрузка .env файла
env_path = Path(__file__).parents[1] / ".env"
load_dotenv(env_path)

SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Strava Authorization</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 40px; }
        .success { color: green; }
    </style>
</head>
<body>
    <h1 class="success">Авторизация успешна!</h1>
    <p>Можете закрыть это окно.</p>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Strava Authorization Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; padding: 40px; }}
        .error {{ color: red; }}
    </style>
</head>
<body>
    <h1 class="error">Ошибка авторизации</h1>
    <p>{error_message}</p>
</body>
</html>
"""


class AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработка ответа от Strava OAuth"""
        try:
            query = parse_qs(urlparse(self.path).query)
            code = query.get("code", [None])[0]

            if code:
                response = requests.post(
                    "https://www.strava.com/oauth/token",
                    data={
                        "client_id": os.getenv("STRAVA_CLIENT_ID"),
                        "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                        "code": code,
                        "grant_type": "authorization_code",
                    },
                )
                response.raise_for_status()
                data = response.json()

                set_key(env_path, "STRAVA_ACCESS_TOKEN", data["access_token"])
                set_key(env_path, "STRAVA_REFRESH_TOKEN", data["refresh_token"])
                set_key(env_path, "STRAVA_TOKEN_EXPIRES_AT", str(data["expires_at"]))

                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(SUCCESS_HTML.encode("utf-8"))

                logger.info("Токены успешно обновлены и сохранены в .env")
            else:
                raise ValueError("Код авторизации не получен")

        except Exception as e:
            logger.error(f"Ошибка авторизации: {e}")
            self.send_response(500)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(ERROR_HTML.format(error_message=str(e)).encode("utf-8"))


def main():
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error("STRAVA_CLIENT_ID или STRAVA_CLIENT_SECRET не найдены в .env")
        return

    server = HTTPServer(("localhost", 8000), AuthHandler)

    SCOPE = "read,read_all,profile:read_all,activity:read_all"
    redirect_uri = "http://localhost:8000"
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope={SCOPE}"

    logger.info("Открываем браузер для авторизации в Strava...")
    webbrowser.open(auth_url)

    try:
        logger.info("Ожидаем ответ от Strava...")
        server.handle_request()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
