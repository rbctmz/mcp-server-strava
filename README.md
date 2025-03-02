# Интеграция Strava API с Model Context Protocol (MCP) SDK

![CI](https://github.com/rbctmz/mcp-server-strava/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)
![License](https://img.shields.io/github/license/Model-Context-Protocol/mcp-strava-integration)

Это приложение демонстрирует интеграцию Strava API с Model Context Protocol SDK для анализа тренировок и получения рекомендаций на основе данных Strava.

## Быстрый старт

1. Установите Python 3.10+
2. Создайте приложение на [Strava API](https://www.strava.com/settings/api)
3. Установите зависимости:

```bash
# Рекомендуемый способ (использует uv для быстрой установки)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install -r requirements-dev.txt

# Альтернативный способ (стандартный pip)
pip install -r requirements.txt
```

4. Установите MCP SDK:

```bash
uv add "mcp[cli]"
```

Альтернативно:

```bash
pip install mcp
```

5. Настройте переменные окружения в `.env`:

```bash
# Скопируйте шаблон
cp .env-template .env

# Отредактируйте .env, добавив ваши данные из Strava API
```

## Настройка Strava API

1. Перейдите на [страницу настроек API](https://www.strava.com/settings/api)
2. Создайте новое приложение:
   - Application Name: MCP Strava Integration
   - Website: [http://localhost](http://localhost)
   - Authorization Callback Domain: localhost
3. После создания вы получите:
   - Client ID
   - Client Secret
4. Для получения Refresh Token:
   ```bash
   # Запустите скрипт авторизации
   python scripts/auth.py
   ```

## Авторизация в Strava API

### 1. Создание приложения

1. Перейдите на [страницу настроек Strava API](https://www.strava.com/settings/api)
2. Создайте новое приложение:
   - Application Name: MCP Strava Integration
   - Category: Training Analysis
   - Website: http://localhost
   - Authorization Callback Domain: localhost
   - Application Description: Интеграция с Claude Desktop для анализа тренировок
3. После создания сохраните:
   - Client ID
   - Client Secret

### 2. Получение токенов доступа

```bash
# Создайте файл с переменными окружения из шаблона
cp .env-template .env

# Добавьте в .env полученные Client ID и Secret
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret

# Запустите скрипт авторизации
python scripts/auth.py
```

При запуске скрипта:
1. Откроется браузер со страницей авторизации Strava
2. Подтвердите доступ к вашим данным
3. После подтверждения токены будут автоматически сохранены в `.env`:
   - `STRAVA_ACCESS_TOKEN`
   - `STRAVA_REFRESH_TOKEN`
   - `STRAVA_TOKEN_EXPIRES_AT`

### 3. Проверка авторизации

```bash
# Запустите сервер в режиме разработки
mcp dev src/server.py

# Проверьте доступ к API
curl -X GET "http://localhost:8000/activities" \
  -H "Authorization: Bearer ${STRAVA_ACCESS_TOKEN}"
```

### 4. Обновление токенов

- Токены обновляются автоматически при истечении срока действия
- Для ручного обновления запустите:
```bash
python scripts/auth.py --refresh
```

### Безопасность

- Храните `.env` файл локально, не добавляйте его в git
- Используйте разные приложения для разработки и продакшена
- Регулярно проверяйте [настройки доступа](https://www.strava.com/settings/apps)
- Используйте rate limiting для соблюдения ограничений API

## Примеры использования

### Получение последних активностей

```python
from mcp import ClientSession

async with ClientSession() as session:
    # Получить список активностей
    activities = await session.read_resource("strava://activities")
    
    # Получить конкретную активность
    activity = await session.read_resource("strava://activities/12345678")
```

### Анализ тренировки

```python
# Через MCP
result = analyze_activity(activity_id="12345678")
"""
Результат:
{
    "type": "Run",
    "distance": 5000,
    "moving_time": 1800,
    "analysis": {
        "pace": 5.5,  # мин/км
        "effort": "Средняя"
    }
}
"""
```

## Запуск MCP сервера

### Установка сервера MCP

```bash
mcp install src/server.py
```

### Запуск в режиме разработки

```bash
mcp dev src/server.py
```

## Разработка

### Запуск тестов

```bash
# Все тесты
pytest

# С отчетом о покрытии
pytest --cov=src

# Конкретный тест
pytest tests/test_server.py -k test_analyze_activity
```

### CI/CD

Проект использует GitHub Actions для:

1. Линтинга (ruff):
   - Проверка форматирования
   - Статический анализ
2. Тестирования (pytest):
   - Unit-тесты
   - Интеграционные тесты
   - Отчет о покрытии

Настройка CI:

1. Перейдите в Settings → Secrets → Actions
2. Добавьте секреты:
   - `STRAVA_CLIENT_ID`
   - `STRAVA_CLIENT_SECRET`
   - `STRAVA_REFRESH_TOKEN`

## Безопасность

- Файл `.env` автоматически добавлен в `.gitignore`
- Токены обновляются автоматически
- Rate limiting: 100 запросов/15 мин, 1000 запросов/день
- Логи не содержат чувствительных данных

## Вопросы и поддержка

- GitHub Issues: [создать issue](https://github.com/rbctmz/mcp-server-strava/issues)
- Telegram: [@](https://t.me/greg_kisel)greg\_kisel



## Лицензия

[MIT](LICENSE)

