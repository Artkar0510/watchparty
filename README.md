# Кино вместе — дипломный проект

Сервис совместного просмотра фильмов. Пользователи формируют список «Хочу посмотреть», находят пересечения со списками друзей и синхронно смотрят выбранный фильм с общим чатом и управлением воспроизведением.

---

## Функциональность

| Возможность | Описание |
|---|---|
| Регистрация и аутентификация | JWT access + refresh токены |
| Список «Хочу посмотреть» | Добавление/удаление фильмов |
| Управление друзьями | Отправка, принятие запросов дружбы |
| Поиск совпадений | Пересечение вотчлистов с друзьями |
| Создание сессии | Хост создаёт комнату просмотра |
| WebSocket синхронизация | Play, Pause, Seek мгновенно у всех участников |
| Чат в реальном времени | Текстовые сообщения во время просмотра |
| Поиск по каталогу | Полнотекстовый поиск через Elasticsearch |
| Кеширование | Redis кеш для списков и деталей фильмов |
| Django Admin | Управление каталогом фильмов и жанров |

---

## Архитектура

```
                        ┌─────────────────────────────────────────────┐
                        │                  Nginx                       │
                        │           (API Gateway, :80)                 │
                        └────┬──────────┬──────────┬──────────┬───────┘
                             │          │          │          │
                    /api/v1/ │          │          │          │ /ws/
                   /auth/    │          │          │          │ /api/v1/sessions/
                   /users/   │          │   /api/v1/films/    │
                             ▼          │   /api/v1/watchlist/ ▼
               ┌─────────────────┐      │   /api/v1/matches/  ┌─────────────────┐
               │  Auth Service   │      ▼        /genres/     │ Together Service│
               │   (FastAPI)     │ ┌─────────────────┐        │   (FastAPI +    │
               │                 │ │ Content Service │        │    WebSocket)   │
               │ JWT auth        │ │   (FastAPI)     │        │                 │
               │ Friendships     │ │                 │        │ Session state   │
               └──────┬──────────┘ │ Film catalog    │        │ Playback sync   │
                      │            │ Watchlist       │        │ Chat messages   │
                      │            │ Match engine    │        └────────┬────────┘
                      │            └──────┬──────────┘                │
                      │                   │                            │
               ┌──────┼──────────┬────────┴──────────────────────────┘
               │      │          │
               ▼      ▼          ▼
        ┌──────────┐ ┌──────────────┐ ┌─────────────┐
        │PostgreSQL│ │Elasticsearch │ │    Redis    │
        │(auth_db) │ │  (movies idx)│ │  (sessions, │
        │(content  │ │              │ │   cache,    │
        │   _db)   │ │              │ │   pub/sub)  │
        └──────────┘ └──────────────┘ └─────────────┘
               ▲              ▲
               │              │
        ┌──────────────────────────┐
        │       ETL Service        │
        │  (PostgreSQL → ES sync)  │
        └──────────────────────────┘

        ┌──────────────────────────┐
        │     Django Admin         │
        │   /admin/ (gunicorn)     │
        └──────────────────────────┘
```

---

## Технологический стек

| Компонент | Технология |
|---|---|
| API-сервисы | Python 3.12, FastAPI, Uvicorn |
| Аутентификация | JWT (python-jose), bcrypt (passlib) |
| Реляционная БД | PostgreSQL 15 (asyncpg) |
| Поиск | Elasticsearch 8 (elasticsearch[async]) |
| Кеш и pub/sub | Redis 7 (redis.asyncio) |
| Real-time | WebSocket (Starlette/FastAPI native) |
| Конфигурация | Pydantic Settings v2 |
| Валидация данных | Pydantic v2 |
| Межсервисные запросы | httpx (async) |
| Admin-панель | Django 5, Gunicorn |
| ETL | psycopg3, elasticsearch-py |
| Reverse proxy | Nginx 1.25 |
| Контейнеризация | Docker, Docker Compose |

---

## Структура проекта

```
graduate_work/
├── docker-compose.yml          # Оркестрация всех сервисов
├── .env.example                # Шаблон переменных окружения
├── init_db/
│   └── 01_init.sql             # Создание баз auth_db и content_db
├── nginx/
│   ├── nginx.conf              # Основная конфигурация Nginx
│   └── conf.d/
│       └── services.conf       # Маршрутизация к сервисам
├── auth_service/               # Аутентификация и дружба
│   ├── core/settings.py        # Pydantic Settings
│   ├── core/security.py        # JWT + bcrypt
│   ├── db/postgres.py          # asyncpg pool + DDL
│   ├── db/redis.py             # Redis клиент
│   ├── api/v1/auth.py          # /register /login /refresh /logout /verify
│   ├── api/v1/users.py         # /me /friends/request /friends/list
│   └── main.py
├── content_service/            # Каталог фильмов и watchlist
│   ├── core/settings.py
│   ├── db/postgres.py          # asyncpg pool + DDL (film_work, genre, watchlist)
│   ├── db/elasticsearch.py     # AsyncElasticsearch + индекс movies
│   ├── db/redis.py
│   ├── api/v1/films.py         # GET /films, GET /films/search, GET /films/{id}
│   ├── api/v1/genres.py        # CRUD жанров
│   ├── api/v1/watchlist.py     # GET/POST/DELETE watchlist
│   ├── api/v1/matches.py       # GET /matches — совпадения с друзьями
│   ├── utils/auth.py           # Проверка токена через auth-service
│   └── main.py
├── together_service/           # Совместный просмотр
│   ├── core/settings.py
│   ├── db/redis.py
│   ├── services/session_manager.py  # CRUD сессий в Redis
│   ├── api/v1/sessions.py      # REST: создать/получить сессию, история чата
│   ├── api/v1/websocket.py     # WS /ws/{session_id}?token=...
│   └── main.py
├── admin_service/              # Django admin
│   ├── config/settings.py
│   ├── movies/models.py        # FilmWork, Genre, GenreFilmWork
│   ├── movies/admin.py         # Регистрация в admin
│   └── movies/migrations/
└── etl/                        # ETL PostgreSQL → Elasticsearch
    ├── core/settings.py
    ├── extractors/postgres.py  # Инкрементальная выборка изменённых фильмов
    ├── loaders/elasticsearch.py # Bulk индексация
    └── main.py                 # Цикл с персистентным состоянием
```

---

## Запуск

### 1. Подготовка

```bash
cp .env.example .env
# Отредактируйте .env — задайте SECRET_KEY и пароли
```

### 2. Запуск всех сервисов

```bash
docker compose up --build
```

### 3. Создание суперпользователя Django

```bash
docker compose exec admin-service python manage.py createsuperuser
```

---

## API

После запуска все эндпоинты доступны через Nginx на `http://localhost:80`.

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
| GET | `/api/v1/films` | Список фильмов (пагинация, сортировка) |
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

### Admin

| URL | Описание |
|---|---|
| `http://localhost/admin/` | Django административная панель |

---

## WebSocket протокол

Подключение: `ws://localhost/ws/{session_id}?token={access_token}`

**Клиент → Сервер:**

```json
{"type": "play",  "position": 42.5}
{"type": "pause", "position": 42.5}
{"type": "seek",  "position": 120.0}
{"type": "chat",  "text": "Отличный момент!"}
{"type": "sync"}
```

**Сервер → Клиент (broadcast):**

```json
{"type": "join",  "user_id": "...", "session": {...}, "timestamp": "..."}
{"type": "play",  "user_id": "...", "position": 42.5, "timestamp": "..."}
{"type": "pause", "user_id": "...", "position": 42.5, "timestamp": "..."}
{"type": "seek",  "user_id": "...", "position": 120.0, "timestamp": "..."}
{"type": "chat",  "user_id": "...", "text": "...", "timestamp": "..."}
{"type": "leave", "user_id": "...", "timestamp": "..."}
{"type": "sync",  "session": {...}}
```

---

## Хранилища данных

### PostgreSQL — auth_db

| Таблица | Назначение |
|---|---|
| `users` | Пользователи (email, username, password_hash) |
| `friendships` | Связи дружбы (requester, addressee, status) |

### PostgreSQL — content_db

| Таблица | Назначение |
|---|---|
| `film_work` | Каталог фильмов и сериалов |
| `genre` | Жанры |
| `genre_film_work` | M2M: жанры ↔ фильмы |
| `watchlist` | Списки «Хочу посмотреть» пользователей |

### Elasticsearch — индекс `movies`

Поля: `title`, `description`, `rating`, `type`, `genres`, `updated_at`

Поиск: multi_match по `title^2` + `description` + `genres` с fuzziness AUTO.

### Redis

| Ключ | Тип | Содержимое |
|---|---|---|
| `session:{id}` | Hash | film_id, host_id, state, position, created_at |
| `session:{id}:participants` | Set | user_id участников |
| `session:{id}:chat` | List | JSON-сообщения (последние 200) |
| `session:{id}:events` | Pub/Sub channel | Broadcast событий воспроизведения |
| `refresh:{user_id}` | String | Refresh токен (с TTL) |
| `films:list:*` | String | Кешированные списки фильмов (TTL 5 мин) |
| `film:{id}` | String | Кешированные детали фильма (TTL 5 мин) |

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
  │◄─ {session_id: "abc"} ──│                        │
  │                          │                        │
  │── WS /ws/abc ───────────►│◄── WS /ws/abc ─────────│
  │                          │── broadcast join ─────►│
  │                          │                        │
  │── {"type":"play",        │                        │
  │    "position": 0} ──────►│                        │
  │                          │── broadcast play ─────►│
  │                          │    position=0          │
  │                          │                        │
  │── {"type":"chat",        │                        │
  │    "text":"Смотри!"} ───►│                        │
  │                          │── broadcast chat ─────►│
  │                          │    "Смотри!"           │
```
