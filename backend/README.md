# Серверная часть

Серверная часть представляет собой FastAPI-модульный монолит, организованный вокруг доменных модулей `identity`, `vocabulary`, `training`, `review`, слоя адаптера `ai` и модуля `graph`.

## Технологический стек

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Celery
- Flower

## Локальный запуск

### 1. Python-окружение

```bash
cd backend
uv sync
```

### 2. Файл окружения

Создай `.env` в папке `backend/`:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:15432/vkr_db?connect_timeout=5
AI_PROVIDER=stub
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=
AI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=20
AI_MAX_RETRIES=1
TRANSLATION_STRICT_REMOTE=true
JWT_SECRET=change_me
JWT_ISSUER=vkr
JWT_ACCESS_TTL_MINUTES=1440
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Шаблон хранится в [`.env.example`](/d:/VKR/VKR_V3_Curs/backend/.env.example).

### 3. Поднять инфраструктуру

Из корня репозитория:

```bash
docker compose up -d postgres redis
```

Перед миграциями убедись, что запущен Docker Desktop и Postgres слушает
`localhost:15432`. Если Docker daemon не запущен, `uv run alembic upgrade head`
не сможет подключиться к базе.

### 4. Применить миграции

```bash
cd backend
uv run alembic upgrade head
```

### 5. Запустить API

```bash
uv run uvicorn app.main:app --reload
```

Серверная часть будет доступна по адресу `http://localhost:8000`.

## Полный запуск через Docker

Из корня репозитория:

```bash
docker compose up -d --build
```

Сервисы:

- серверная часть: `http://localhost:8000`
- клиентское приложение: `http://localhost:5173`
- единая локальная точка входа: `http://localhost:8080`
- Flower: `http://localhost:5555`
- PostgreSQL: `localhost:15432`
- Redis: `localhost:6379`

## Режим разработки

Для автоматической перезагрузки и подключения локального кода в контейнер:

```bash
docker compose -f ../docker-compose.yml -f ../docker-compose.dev.yml up --build
```

Этот режим:

- подключает код серверной части в контейнер
- запускает Alembic перед uvicorn
- использует автоматическую перезагрузку uvicorn
- поднимает рабочий процесс Celery в режиме, удобном для разработки

## Настройка AI

Весь доступ к AI централизован в `app.modules.ai`. В архитектуре серверной части это слой адаптера: он скрывает детали внешнего провайдера и резервной логики от доменных модулей.

Поддерживаемые провайдеры:

- `stub`: локальное детерминированное поведение
- `openai_compatible`: внешний `/chat/completions`
- `ollama`: локальный или удаленный HTTP-адрес, совместимый с Ollama

### Текущая философия использования AI

Серверная часть использует LLM как специализированный инструмент для задач, где важна семантика или генерация текста.

Текущее поведение гибридное:

- локальные эвристики и базовый лексикон обрабатывают простые случаи перевода
- внешний AI используется для семантической неоднозначности, генерации предложений и поясняющей обратной связи там, где от этого есть реальная польза
- для `context_definition` используется стратегия: сначала переиспользовать готовое определение, затем при необходимости обратиться к LLM

### Стратегия получения `context_definition`

При создании элемента словаря:

1. Система ищет существующие определения для той же леммы в общем словаре (`dictionary_entries`).
2. Кандидаты оцениваются по совпадению перевода и пересечению контекста.
3. Если найден надёжный кандидат (score ≥ 0.72), определение переиспользуется.
4. Иначе вызывается AI и строится новое определение.

## Фоновые задачи

Тяжелые операции выполняются через Celery:

- создание словарных элементов с AI
- генерация упражнений

Статус задачи доступен через `/api/v1/tasks/{task_id}`.

Владение задачами принудительно контролируется:

- каждая поставленная задача связана с `owner_user_id`
- только владелец может опрашивать ее статус

## Основные API-группы

### Identity / Auth
- POST /api/v1/auth/token
- POST /api/v1/auth/login-or-register
- POST /api/v1/auth/verify
- GET  /api/v1/auth/me

### Пользователи
- GET  /api/v1/users
- GET  /api/v1/users/{user_id}
- POST /api/v1/users

### Vocabulary
- GET    /api/v1/vocabulary/me
- GET    /api/v1/vocabulary
- POST   /api/v1/vocabulary/me           (202 Accepted, Celery task)
- PUT    /api/v1/vocabulary/me/{item_id}
- DELETE /api/v1/vocabulary/me/{item_id}
- POST   /api/v1/vocabulary/me/from-capture (202 Accepted, Celery task)

### Перевод
- POST /api/v1/translate/me
- POST /api/v1/translate

### Упражнения и сессии (модуль training)
- POST /api/v1/exercises/me/generate     (202 Accepted, Celery task)
- POST /api/v1/exercises/generate        (202 Accepted, Celery task)
- POST /api/v1/sessions/submit
- GET  /api/v1/sessions
- GET  /api/v1/sessions/me
- GET  /api/v1/sessions/{session_id}/answers
- GET  /api/v1/sessions/me/{session_id}/answers

### Повторение и SRS (модуль review)
- GET  /api/v1/context/me/review-queue
- POST /api/v1/context/me/review-queue/submit
- POST /api/v1/context/me/review-queue/submit-bulk
- POST /api/v1/context/me/review-session/start
- GET  /api/v1/context/me/review-plan
- GET  /api/v1/context/me/progress
- GET  /api/v1/context/me/review-summary
- GET  /api/v1/context/me/word-progress
- GET  /api/v1/context/me/word-progress/{word}
- DELETE /api/v1/context/me/word-progress/{word}

### Learning Graph (модуль graph)
- GET  /api/v1/learning-graph/me/interests
- PUT  /api/v1/learning-graph/me/interests
- POST /api/v1/learning-graph/me/semantic-upsert
- GET  /api/v1/learning-graph/me/interest-words
- GET  /api/v1/learning-graph/me/anchors

### AI
- GET  /api/v1/ai/status
- POST /api/v1/ai/explain-error

### Фоновые задачи
- GET /api/v1/tasks/{task_id}

В текущей версии `graph` используется как компактный семантический профиль:

- интересы пользователя выводятся из сохраненной лексики и контекстов
- `WordSense` отделяет разные значения одной леммы
- смысловые связи показывают полисемию и слова из той же темы
- SRS-расписание и учет ошибок остаются в модуле `review`

## Проверки и тесты

### Тесты

```bash
uv run pytest -q
```

Текущий тестовый контур в основном интеграционный и использует SQLite in-memory.

## Дополнительные материалы

Подробности по слоям, границам модулей и ограничениям среды выполнения смотри в [ARCHITECTURE.md](ARCHITECTURE.md).
