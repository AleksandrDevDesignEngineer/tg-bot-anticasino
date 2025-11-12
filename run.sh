#!/bin/bash

# Скрипт для сборки и запуска бота в Docker

# Собираем образ
docker build -t casino-bot .

# Запускаем контейнер
docker run -d \
  --name casino-bot \
  -e TOKEN="YOUR_BOT_TOKEN" \  # Замените на реальный токен
  -v bot-data:/app/data \
  --restart unless-stopped \
  casino-bot

# Просмотр логов
docker logs -f casino-bot