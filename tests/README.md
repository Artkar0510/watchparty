# Happy-path интеграционные тесты

End-to-end тесты, гоняющие реальный стек через nginx. Покрывают:

- `auth-service`: регистрация, логин, refresh, /verify
- `auth-service`: дружба (request → accept)
- `content-service`: создание фильма, watchlist, matches с другом
- `together-service`: создание сессии, WebSocket play/pause/chat синхронизация между двумя клиентами
- `ugc-service`: лайки и закладки
- `notification-service`: уведомление о friend.request, прилетающее через RabbitMQ → worker → Redis

## Запуск

```bash
# 1. Поднять весь стек
docker compose up -d --build
# (подождать ~30 сек пока поднимутся elasticsearch и postgres)

# 2. Из корня проекта:
pip install -r tests/requirements.txt
pytest tests/
```

## Переменные окружения

| Переменная | Default | Описание |
|---|---|---|
| `BASE_URL` | `http://localhost:8000` | Адрес nginx |
| `WS_URL` | `ws://localhost:8000` | WebSocket-адрес |
