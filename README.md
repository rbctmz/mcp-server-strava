# Интеграция Strava API с Model Context Protocol (MCP) SDK

![CI](https://github.com/rbctmz/mcp-server-strava/actions/workflows/ci.yml/badge.svg)
![Codecov](https://codecov.io/gh/rbctmz/mcp-server-strava/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)

Интеграция для анализа тренировок и получения рекомендаций на основе данных Strava с использованием Model Context Protocol SDK.

## 🚀 Возможности

- Анализ тренировок из Strava
- Рекомендации по тренировкам
- Автоматическое обновление токенов
- Rate limiting для API запросов

## 📋 Требования

- Python 3.10+
- [Claude Desktop](https://claude.ai/desktop)
- [Strava](https://www.strava.com) аккаунт
- [uv](https://github.com/astral-sh/uv) (рекомендуется)

## ⚙️ Установка

```bash
# Клонируем репозиторий
git clone https://github.com/rbctmz/mcp-server-strava.git
cd mcp-server-strava

# Установка через uv (рекомендуется)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install .

# Установка в режиме разработки
uv pip install -e ".[dev]"
```

### Установка MCP SDK

```bash
uv add "mcp[cli]"
```

### Настройка окружения

```bash
# Скопируйте шаблон
cp .env-template .env

# Отредактируйте .env, добавив ваши данные из Strava API
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

## Настройка Strava API

1. Перейдите на [страницу настроек API](https://www.strava.com/settings/api)
2. Создайте новое приложение:
   - Application Name: MCP Strava Integration
   - Category: Training Analysis
   - Website: http://localhost
   - Authorization Callback Domain: localhost
   - Application Description: Интеграция с Claude Desktop для анализа тренировок
3. После создания сохраните:
   - Client ID
   - Client Secret
4. Для получения Refresh Token:
   
   ```bash
   python scripts/auth.py
   ```

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

### Ресурсы

| Ресурс | Описание |
|--------|----------|
| `strava://activities` | Список последних активностей |
| `strava://activities/{id}` | Детали конкретной активности |

### Инструменты

| Инструмент | Описание |
|------------|----------|
| `analyze_activity(activity_id)` | Анализ отдельной тренировки |
| `analyze_training_load(activities)` | Анализ тренировочной нагрузки |
| `get_activity_recommendations()` | Рекомендации по тренировкам |

### Примеры использования

#### Получение активностей

```python
from mcp import ClientSession

async with ClientSession() as session:
    # Получить список активностей
    activities = await session.read_resource("strava://activities")
    
    # Получить конкретную активность
    activity = await session.read_resource("strava://activities/12345678")
```

#### Анализ тренировки

```python
# Анализ одной тренировки
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

# Анализ тренировочной нагрузки
summary = analyze_training_load(activities)
"""
{
    "activities_count": 10,
    "total_distance": 50.5,  # км
    "total_time": 5.2,      # часы
    "heart_rate_zones": {
        "easy": 4,    # ЧСС < 120
        "medium": 4,  # ЧСС 120-150
        "hard": 2     # ЧСС > 150
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
# Все тесты с отчетом о покрытии
pytest --cov=src --cov-report=html

# Текущее покрытие: 69%
# - src/server.py: 69% (173 строки)
# - src/__init__.py: 100%

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

#### Проверки в GitHub Actions

| Тип проверки | Инструмент | Описание |
|--------------|------------|-----------|
| Линтинг | ruff | Форматирование и статический анализ |
| Тесты | pytest | Unit и интеграционные тесты |
| Покрытие | pytest-cov | Отчет о покрытии кода тестами |

#### Текущее состояние

- ![Coverage](https://img.shields.io/badge/coverage-69%25-yellow.svg)
- ![Tests](https://img.shields.io/badge/tests-12%20passed-green.svg)
- ![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)

⚠️ **Важные правила**:

1. Защита токенов:
   - `.env` в `.gitignore`
   - Используйте GitHub Secrets
   - Не коммитьте реальные значения

2. Rate limiting:
   - 100 запросов/15 мин
   - 1000 запросов/день
   - Автоматический контроль

3. Секреты в CI:
   ```ini
   STRAVA_CLIENT_ID=<client_id>
   STRAVA_CLIENT_SECRET=<client_secret>
   STRAVA_REFRESH_TOKEN=<refresh_token>
   ```

#### Настройка секретов на GitHub

1. Перейдите в `Settings → Secrets → Actions` вашего репозитория
2. Для каждого секрета:
   - Нажмите `New repository secret`
   - Добавьте реальные значения из вашего `.env` файла:

     ```
     Name: STRAVA_CLIENT_ID
     Value: <ваш реальный Client ID из Strava>
     ```

   - Повторите для `STRAVA_CLIENT_SECRET` и `STRAVA_REFRESH_TOKEN`

⚠️ **Важно**:

- В GitHub Secrets добавляйте реальные значения
- В документации и коде используйте только плейсхолдеры
- Никогда не коммитьте реальные значения в репозиторий
- Секреты в GitHub хранятся в зашифрованном виде
- Значения секретов нельзя просмотреть после сохранения

#### Секреты для CI/CD

В GitHub Actions используются три ключевых секрета:

1. `STRAVA_CLIENT_ID` и `STRAVA_CLIENT_SECRET`:
   - Идентификаторы вашего приложения в Strava
   - Необходимы для OAuth 2.0 аутентификации
   - Используются при обновлении токенов

2. `STRAVA_REFRESH_TOKEN`:
   - Долгоживущий токен для обновления доступа
   - Не имеет срока действия
   - Используется для автоматического получения `access_token`

⚠️ **Примечание**: `STRAVA_ACCESS_TOKEN` не добавляется в секреты, так как:

- Имеет ограниченный срок действия (6 часов)
- Автоматически обновляется через `refresh_token`
- Генерируется при запуске тестов

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

## Лицензия

[MIT](LICENSE)

## 🛠 Разработка

### Contributing

1. Форкните репозиторий
2. Установите зависимости разработки:
   ```bash
   uv pip install -e ".[dev]"
   ```
3. Создайте ветку для ваших изменений:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. Убедитесь что:
   - Код отформатирован (`ruff format .`)
   - Линтер проходит (`ruff check .`)
   - Тесты проходят (`pytest`)
   - Документация обновлена
5. Создайте Pull Request

### Запуск тестов

```bash
# Все тесты с отчетом о покрытии
pytest --cov=src --cov-report=html

# Текущее покрытие:
# - Общее: 69%
# - src/server.py: 69% (173 строки)
# - src/__init__.py: 100%

# Запуск конкретного теста
pytest tests/test_server.py -k test_analyze_activity
```

## 📫 Поддержка

- GitHub Issues: [создать issue](https://github.com/rbctmz/mcp-server-strava/issues)
- Telegram: [@greg_kisel](https://t.me/greg_kisel)

## 📄 Лицензия

[MIT](LICENSE)