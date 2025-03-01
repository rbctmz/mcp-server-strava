# Интеграция Strava API с Model Context Protocol (MCP) SDK

![CI](https://github.com/rbctmz/mcp-server-strava/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)

Это приложение демонстрирует интеграцию Strava API с Model Context Protocol SDK для анализа тренировок и получения рекомендаций на основе данных Strava.

## Функциональность

Проект позволяет:
1. Получать последние активности из Strava
2. Анализировать отдельные тренировки
3. Получать общую статистику тренировочной нагрузки
4. Формировать рекомендации на основе анализа тренировок

## Установка

### Предварительные требования

- Python 3.10 или выше
- Доступ к API Strava (Client ID, Client Secret, Refresh Token)
- MCP SDK

### Установка зависимостей

```bash
pip install mcp-sdk requests python-dotenv
```

```zsh
uv add "mcp[cli]"
```

You can install this server in Claude Desktop and interact with it right away by running:

```bash
mcp install server.py
```

Alternatively, you can test it with the MCP Inspector:

```bash
mcp dev server.py
```


### Настройка переменных окружения

Создайте файл `.env` в корневой директории проекта:

```
STRAVA_CLIENT_ID=ваш_client_id
STRAVA_CLIENT_SECRET=ваш_client_secret
STRAVA_REFRESH_TOKEN=ваш_refresh_token
STRAVA_ACCESS_TOKEN=начальный_access_token
STRAVA_TOKEN_EXPIRES_AT=время_истечения_токена
```

## Основной функционал

### Ресурсы MCP

- `strava://activities` - Получение списка последних активностей
- `strava://activities/{activity_id}` - Получение информации о конкретной активности

### Инструменты MCP

- `analyze_activity` - Анализ отдельной активности (тип, дистанция, время, темп, нагрузка)
- `analyze_training_load` - Анализ общей тренировочной нагрузки (статистика по типам активностей, зонам ЧСС)
- `get_activity_recommendations` - Получение рекомендаций по тренировкам

## Запуск

```bash
python src/server.py
```

## Анализ тренировочной нагрузки

Система анализирует следующие параметры:
- Количество активностей
- Общую дистанцию (в километрах)
- Общее время тренировок (в часах)
- Распределение по типам активностей
- Распределение по зонам ЧСС:
  - Легкая (ЧСС < 120)
  - Средняя (ЧСС 120-150)
  - Высокая (ЧСС > 150)

## CI/CD

Проект использует GitHub Actions для:
- Проверки форматирования кода (ruff)
- Запуска автоматических тестов (pytest)
- Проверки на разных версиях Python

Для работы CI необходимо настроить секреты в настройках репозитория:
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REFRESH_TOKEN`

## Безопасность

- Автоматическое обновление access token при истечении
- Безопасное хранение учетных данных через переменные окружения
- Не включайте файл `.env` в систему контроля версий

## Лицензия

[MIT](LICENSE)
