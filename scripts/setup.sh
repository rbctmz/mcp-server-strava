#!/bin/bash
set -e

# Проверяем наличие uv
if ! command -v uv &> /dev/null; then
    echo "Устанавливаем uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Добавляем uv в PATH если его там нет
UV_PATH="/Users/gregkisel/.local/bin"
if [[ ":$PATH:" != *":$UV_PATH:"* ]]; then
    echo "export PATH=\"\$PATH:$UV_PATH\"" >> ~/.zshrc
    source ~/.zshrc
fi

# Устанавливаем зависимости
uv pip install -r requirements-dev.txt

echo "Установка завершена!"