# Кино вместе — дипломный проект

Сервис совместного просмотра фильмов. Пользователи формируют список «Хочу посмотреть», находят пересечения со списками друзей и синхронно смотрят выбранный фильм с общим чатом и управлением воспроизведением. Помимо основного сценария реализованы пользовательский контент (лайки, закладки, рецензии) и уведомления.

---

## Функциональность

| Возможность | Описание |
|---|---|
| Регистрация и аутентификация | JWT access + refresh токены |
| Дружба | Запросы / принятие, список друзей |
| Список «Хочу посмотреть» | Добавление/удаление фильмов |
| Поиск совпадений | Пересечение вотчлистов с друзьями |
| Создание сессии | Хост создаёт комнату просмотра |
| WebSocket синхронизация | Play, Pause, Seek мгновенно у всех участников |
| Чат в реальном времени | Текстовые сообщения во время просмотра |
| Поиск по каталогу | Полнотекстовый поиск через Elasticsearch |
| UGC | Лайки, закладки, рецензии (MongoDB) |
| Уведомления | Worker-консьюмер RabbitMQ → Redis-хранилище |
| Кеширование | Redis-кеш для списков и деталей фильмов |
| Django Admin | Управление каталогом фильмов и жанров |
| Observability | Структурированное JSON-логирование, Sentry-интеграция |

---

## Архитектура

```
                       ┌────────────────────────────────────────────────┐
                       │                    Nginx                        │
                       │                (API Gateway, :80)               │
                       └─┬──────┬───────┬──────┬──────┬──────┬───────────┘
                         │      │       │      │      │      │
                  /auth/ │      │ /films│ /ws/ │ /likes      │ /notifications/
                  /users/│      │ /watch│      │ /bookmarks  │
                         ▼      ▼ /match▼      ▼ /reviews    ▼
                ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
                │  Auth    │ │ Content  │ │ Together │ │   UGC    │ │ Notification │
                │ FastAPI  │ │ FastAPI  │ │ FastAPI  │ │ FastAPI  │ │   FastAPI    │
                │          │ │          │ │   + WS   │ │          │ │   + worker   │
                └──┬───┬───┘ └──┬───┬─┬─┘ └────┬─────┘ └────┬─────┘ └──┬────────┬──┘
                   │   │        │   │ │        │            │          │        │
                   │   │        │   │ │        │            │          │        │
        ┌──────────┼───┼────────┼───┼─┼────────┼────────────┼──────────┼────┐   │
        │          │   │        │   │ │        │            │          │    │   │
        ▼          ▼   ▼        ▼   ▼ ▼        ▼            ▼          ▼    ▼   ▼
   ┌────────┐ ┌────────┐ ┌──────────┐ ┌─────────────┐ ┌────────────┐  ┌─────────┐
   │Postgres│ │ Redis  │ │   ETL    │ │   MongoDB   │ │  RabbitMQ  │  │  Redis  │
   │auth_db │ │ cache  │ │ PG → ES  │ │ likes/marks │ │ topic xchg │  │ notifs  │
   │content_db│ pub/sub│ └─────┬────┘ │   reviews   │ │            │  │  store  │
   └────┬───┘ └────────┘       │      └─────────────┘ └─────┬──────┘  └─────────┘
        │                      ▼                            │
        │              ┌──────────────┐                     │
        │              │Elasticsearch │                     │
        │              │ movies index │                     │
        │              └──────────────┘                     │
        │                                                   │
        ▼                                                   │
┌──────────────┐                                            │
│ Django Admin │   ──── all FastAPI services publish        │
│  (gunicorn)  │        events to RabbitMQ topic exchanges  │
└──────────────┘        (auth.events / together.events /    │
                         ugc.events) — consumed by ─────────┘
                         notification-worker
```

---

## Технологический стек

| Компонент | Технология |
|---|---|
| API-сервисы | Python 3.12, FastAPI, Uvicorn |
| Аутентификация | JWT (python-jose), bcrypt (passlib) |
| Реляционные БД | PostgreSQL 15 (asyncpg) |
| Документоориентированная БД | MongoDB 7 (motor) |
| Поиск | Elasticsearch 8 (elasticsearch[async]) |
| Кеш / pub/sub | Redis 7 (redis.asyncio) |
| Брокер событий | RabbitMQ 3.13 (aio-pika) |
| Real-time | WebSocket (Starlette/FastAPI native) + Redis pub/sub |
| Миграции SQL | Alembic |
| Конфигурация | Pydantic Settings v2 |
| Валидация данных | Pydantic v2 |
| Межсервисные запросы | httpx (async) |
| Admin-панель | Django 5, Gunicorn |
| ETL | psycopg3, elasticsearch-py |
| Reverse proxy | Nginx 1.25 |
| Контейнеризация | Docker, Docker Compose |
| Логи | logging.config.dictConfig + JSON-формат |
| Мониторинг ошибок | Sentry SDK |
| Тесты | pytest, pytest-asyncio, httpx, websockets |

---

## Структура проекта

```
graduate_work/
├── docker-compose.yml          # Оркестрация всех сервисов
├── .env.example                # Шаблон переменных окружения
├── init_db/01_init.sql         # Создание баз auth_db и content_db
├── nginx/                      # API Gateway
│   ├── nginx.conf
│   └── conf.d/services.conf
├── auth_service/               # Аутентификация и дружба (FastAPI + Postgres + Redis)
│   ├── alembic/                # Миграции (users, friendships)
│   ├── core/{settings,security,logger}.py
│   ├── db/{postgres,redis}.py
│   ├── api/v1/{auth,users}.py
│   ├── services/notifier.py    # Публикация в RabbitMQ (auth.events)
│   └── main.py
├── content_service/            # Каталог + watchlist + matches (FastAPI + Postgres + ES)
│   ├── alembic/                # Миграция (watchlist)
│   ├── core/{settings,logger}.py
│   ├── db/{postgres,elasticsearch,redis}.py
│   ├── api/v1/{films,genres,watchlist,matches}.py
│   ├── utils/auth.py
│   └── main.py
├── together_service/           # Совместный просмотр (FastAPI + WS + Redis pub/sub)
│   ├── core/{settings,logger}.py
│   ├── db/redis.py
│   ├── services/{session_manager,notifier}.py
│   ├── api/v1/{sessions,websocket}.py
│   └── main.py
├── ugc_service/                # UGC: лайки, закладки, рецензии (FastAPI + MongoDB)
│   ├── core/{settings,logger}.py
│   ├── db/mongo.py
│   ├── services/notifier.py
│   ├── api/v1/{likes,bookmarks,reviews}.py
│   └── main.py
├── notification_service/       # Уведомления (FastAPI API + RabbitMQ worker + Redis)
│   ├── core/{settings,logger}.py
│   ├── db/redis.py
│   ├── services/store.py       # Хранилище уведомлений в Redis
│   ├── api/v1/notifications.py
│   ├── worker/main.py          # Консьюмер RabbitMQ (auth/ugc/together.events)
│   └── main.py
├── admin_service/              # Django admin
│   ├── config/{settings,logger,urls,wsgi}.py
│   └── movies/{models,admin,migrations}/
├── etl/                        # ETL PostgreSQL → Elasticsearch
│   ├── core/{settings,logger}.py
│   ├── extractors/postgres.py
│   ├── loaders/elasticsearch.py
│   └── main.py
└── tests/                      # Happy-path интеграционные тесты
    ├── conftest.py             # alice / bob / friends / film fixtures
    ├── test_auth_flow.py
    ├── test_friends.py
    ├── test_watchlist_and_matches.py
    ├── test_sessions_websocket.py
    ├── test_ugc.py
    └── test_notifications.py
```

---

## Запуск

### 1. Подготовка

```bash
cp .env.example .env
# Отредактируйте .env — задайте SECRET_KEY и пароли для prod
```

### 2. Запуск всех сервисов

```bash
docker compose up --build
```

### 3. Создание суперпользователя Django

```bash
docker compose exec admin-service python manage.py createsuperuser
```

### 4. Запуск тестов

```bash
pip install -r tests/requirements.txt
pytest tests/
```

См. также [tests/README.md](tests/README.md).

---

## API

После запуска все эндпоинты доступны через Nginx на `http://localhost:8000`.

### Auth Service

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/v1/auth/register` | Регистрация |
| POST | `/api/v1/auth/login` | Вход, получение токенов |
| POST | `/api/v1/auth/refresh` | Обновление access-токена |
| POST | `/api/v1/auth/logout` | Выход (инвалидация refresh) |
| GET  | `/api/v1/users/me` | Текущий пользователь |
| POST | `/api/v1/users/friends/request` | Отправить запрос дружбы |
| PATCH | `/api/v1/users/friends/{id}/accept` | Принять запрос |
| GET  | `/api/v1/users/friends/list` | Список друзей |

### Content Service

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/v1/films` | Список фильмов |
| GET | `/api/v1/films/search?query=...` | Полнотекстовый поиск (Elasticsearch) |
| GET | `/api/v1/films/{id}` | Детали фильма |
| POST | `/api/v1/films` | Создать фильм |
| GET | `/api/v1/genres` | Список жанров |
| GET | `/api/v1/watchlist` | Мой список «Хочу посмотреть» |
| POST | `/api/v1/watchlist` | Добавить фильм в список |
| DELETE | `/api/v1/watchlist/{film_id}` | Удалить из списка |
| GET | `/api/v1/matches` | Совпадения со списками друзей |

### Together Service

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/v1/sessions` | Создать сессию просмотра |
| GET | `/api/v1/sessions/{id}` | Состояние сессии |
| GET | `/api/v1/sessions/{id}/chat` | История чата |
| WS  | `/ws/{session_id}?token=...` | WebSocket синхронизация |

### UGC Service

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/v1/likes/{film_id}` | Лайк фильму |
| DELETE | `/api/v1/likes/{film_id}` | Снять лайк |
| GET | `/api/v1/likes/film/{film_id}` | Количество лайков фильма |
| GET | `/api/v1/likes/me` | Мои лайки |
| POST | `/api/v1/bookmarks` | Добавить в закладки |
| GET | `/api/v1/bookmarks` | Мои закладки |
| DELETE | `/api/v1/bookmarks/{film_id}` | Убрать из закладок |
| POST | `/api/v1/reviews/{film_id}` | Оставить рецензию |
| GET | `/api/v1/reviews/film/{film_id}` | Рецензии фильма |
| DELETE | `/api/v1/reviews/{film_id}` | Удалить свою рецензию |

### Notification Service

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/v1/notifications` | Мои уведомления + счётчик непрочитанных |
| POST | `/api/v1/notifications/read` | Пометить все как прочитанные |

### Admin

| URL | Описание |
|---|---|
| `http://localhost:8000/admin/` | Django административная панель |

---

## События RabbitMQ

| Exchange | Routing key | Источник | Назначение |
|---|---|---|---|
| `auth.events` | `friend.request` | auth-service | уведомление addressee |
| `auth.events` | `friend.accepted` | auth-service | уведомление requester |
| `together.events` | `session.created` | together-service | уведомление приглашённых |
| `ugc.events` | `like.created` | ugc-service | (зарезервировано) |
| `ugc.events` | `review.created` | ugc-service | (зарезервировано) |

`notification-worker` подписан на все эти exchange'ы (topic, durable), получает сообщения и пишет уведомления в Redis (`notifications:{user_id}` LIST + счётчик непрочитанных).

---

## WebSocket протокол

Подключение: `ws://localhost:8000/ws/{session_id}?token={access_token}`

**Клиент → Сервер:**

```json
{"type": "play",  "position": 42.5}
{"type": "pause", "position": 42.5}
{"type": "seek",  "position": 120.0}
{"type": "chat",  "text": "Отличный момент!"}
{"type": "sync"}
```

**Сервер → Клиент (broadcast через Redis pub/sub):**

```json
{"type": "join",  "user_id": "...", "session": {...}, "timestamp": "..."}
{"type": "play",  "user_id": "...", "position": 42.5, "timestamp": "..."}
{"type": "pause", "user_id": "...", "position": 42.5, "timestamp": "..."}
{"type": "seek",  "user_id": "...", "position": 120.0, "timestamp": "..."}
{"type": "chat",  "user_id": "...", "text": "...", "timestamp": "..."}
{"type": "leave", "user_id": "...", "timestamp": "..."}
```

Все события транслируются через Redis pub/sub-канал `session:{id}:events`. Каждый инстанс `together-service` подписывается на канал и форвардит входящие сообщения только своим локальным WebSocket-клиентам — это позволяет горизонтально масштабировать сервис.

---

## Хранилища данных

### PostgreSQL — auth_db

| Таблица | Назначение |
|---|---|
| `users` | Пользователи (email, username, password_hash) |
| `friendships` | Связи дружбы (requester, addressee, status) |

Миграции: `auth_service/alembic/versions/` (alembic upgrade head на старте контейнера).

### PostgreSQL — content_db

| Таблица | Источник | Назначение |
|---|---|---|
| `film_work`, `genre`, `genre_film_work` | Django migrations (admin_service) | Каталог фильмов и жанров |
| `watchlist` | Alembic (content_service) | Списки «Хочу посмотреть» |

### Elasticsearch — индекс `movies`

Поля: `title`, `description`, `rating`, `type`, `genres`, `updated_at`. Поиск: multi_match по `title^2` + `description` + `genres` с fuzziness AUTO. Индекс заполняется ETL-сервисом из `content_db.film_work`.

### MongoDB — `ugc_db`

| Коллекция | Поля | Индексы |
|---|---|---|
| `likes` | `user_id`, `film_id`, `created_at` | unique(user_id, film_id), film_id |
| `bookmarks` | `user_id`, `film_id`, `created_at` | unique(user_id, film_id), user_id |
| `reviews` | `user_id`, `film_id`, `text`, `rating`, `created_at` | unique(user_id, film_id), (film_id, created_at desc) |

### Redis

| Ключ | Тип | Назначение |
|---|---|---|
| `session:{id}` | Hash | film_id, host_id, state, position, created_at |
| `session:{id}:participants` | Set | user_id участников |
| `session:{id}:chat` | List | JSON-сообщения (последние 200) |
| `session:{id}:events` | Pub/Sub channel | Broadcast событий воспроизведения |
| `refresh:{user_id}` | String | Refresh-токен (с TTL) |
| `films:list:*`, `film:{id}` | String | Кеш списков и деталей фильмов |
| `notifications:{user_id}` | List | JSON-уведомления (последние 200) |
| `notifications:{user_id}:unread` | String | Счётчик непрочитанных |

---

## Observability

### Логирование

Все Python-сервисы используют `logging.config.dictConfig` с собственным `JsonFormatter` (см. `*/core/logger.py`, у Django — `admin_service/config/logger.py`). Каждая запись содержит `timestamp`, `level`, `logger`, `service`, `message` и сериализуется одной строкой JSON в stdout — удобно для сбора в ELK / Loki / CloudWatch.

### Sentry

Все FastAPI-сервисы инициализируют Sentry SDK при старте, если задана переменная `SENTRY_DSN` (`sentry-sdk[fastapi]`). Настраивается через переменные окружения:

```
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
```

Для трассировки/метрик возможна интеграция OpenTelemetry (Python OTel auto-instrumentation для FastAPI / asyncpg / motor / aio-pika) — настраивается отдельно через `OTEL_EXPORTER_OTLP_ENDPOINT` и `opentelemetry-instrumentation-*` пакеты, в проекте оставлено как hook на будущее.

---

## Диаграмма сценария «Кино вместе»

```
Алиса                    Сервер                    Боб
  │                         │                        │
  │── POST /watchlist ──────►│                        │
  │   (добавил Inception)    │                        │
  │                          │◄── POST /watchlist ────│
  │                          │    (добавил Inception) │
  │                          │                        │
  │── GET /matches ─────────►│                        │
  │◄─ [{film: Inception,     │                        │
  │     friends: [Bob]}] ───│                        │
  │                          │                        │
  │── POST /sessions ───────►│                        │
  │   {invited: [bob_id]}    │                        │
  │                          │── publish ────────────►│ rabbit: session.created
  │                          │                        │ → worker → notif:bob
  │                          │                        │
  │── WS /ws/abc ───────────►│◄── WS /ws/abc ─────────│
  │                          │── broadcast join ─────►│ через Redis pub/sub
  │                          │                        │
  │── {"type":"play",        │                        │
  │    "position": 0} ──────►│                        │
  │                          │── broadcast play ─────►│
  │                          │                        │
  │── {"type":"chat",        │                        │
  │    "text":"Смотри!"} ───►│                        │
  │                          │── broadcast chat ─────►│
```
