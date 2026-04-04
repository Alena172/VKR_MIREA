# Backend

Backend - это FastAPI-модульный монолит, который отвечает за аутентификацию, словарь, перевод, генерацию упражнений, поток повторения и API фоновых задач.

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
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### 2. Файл окружения

Создай `.env` в папке `backend/`:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:15432/vkr_db
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

### 4. Применить миграции

```bash
cd backend
alembic upgrade head
```

### 5. Запустить API

```bash
uvicorn app.main:app --reload
```

Backend будет доступен по адресу `http://localhost:8000`.

## Полный запуск через Docker

Из корня репозитория:

```bash
docker compose up -d --build
```

Сервисы:

- backend: `http://localhost:8000`
- frontend: `http://localhost:5173`
- gateway: `http://localhost:8080`
- Flower: `http://localhost:5555`
- PostgreSQL: `localhost:15432`
- Redis: `localhost:6379`

## Режим разработки

Для autoreload и bind mount:

```bash
docker compose -f ../docker-compose.yml -f ../docker-compose.dev.yml up --build
```

Этот режим:

- монтирует backend-код в контейнер
- запускает Alembic перед uvicorn
- использует reload в uvicorn
- поднимает Celery worker с dev-friendly solo pool

## Настройка AI

Весь доступ к AI централизован в `app.modules.ai_services`.

Поддерживаемые провайдеры:

- `stub`: локальное детерминированное поведение
- `openai_compatible`: внешний `/chat/completions`
- `ollama`: локальный или удаленный endpoint, совместимый с Ollama

### Текущая философия использования AI

Backend не считает LLM универсальным решением для всех задач.

Текущее поведение гибридное:

- локальные эвристики и `base_lexicon` обрабатывают простые случаи перевода
- внешний AI используется для семантической неоднозначности, генерации предложений и поясняющего feedback там, где от этого есть реальная польза
- для `context_definition` используется стратегия `reuse-first, LLM-fallback`

### Стратегия получения `context_definition`

При создании элемента словаря:

1. backend ищет уже существующие определения для той же леммы в словаре пользователя
2. кандидаты оцениваются по переводу и пересечению контекста
3. если найден надежный кандидат, определение переиспользуется
4. иначе вызывается AI и строится новое определение

Вместе с определением сохраняются метаданные:

- `context_definition_source`
- `context_definition_confidence`
- `definition_reused_from_item_id`

## Фоновые задачи

Тяжелые операции выполняются через Celery:

- создание словарных элементов с AI
- оркестрация для capture -> vocabulary
- генерация упражнений

Статус задачи доступен через `/api/v1/tasks/{task_id}`.

Владение задачами принудительно контролируется:

- каждая поставленная задача связана с `owner_user_id`
- только владелец может опрашивать ее статус

## Основные API-группы

### Auth

- `POST /api/v1/auth/token`
- `POST /api/v1/auth/login-or-register`
- `POST /api/v1/auth/verify`
- `GET /api/v1/auth/me`

### Vocabulary

- `GET /api/v1/vocabulary/me`
- `POST /api/v1/vocabulary/me`
- `PUT /api/v1/vocabulary/me/{item_id}`
- `DELETE /api/v1/vocabulary/me/{item_id}`
- `POST /api/v1/vocabulary/me/from-capture`

### Translation

- `POST /api/v1/translate/me`

### Exercises и sessions

- `POST /api/v1/exercises/me/generate`
- `POST /api/v1/sessions/submit`
- `GET /api/v1/sessions/me`
- `GET /api/v1/sessions/me/{session_id}/answers`

### Review и SRS

- `GET /api/v1/context/me/recommendations`
- `GET /api/v1/context/me/review-queue`
- `POST /api/v1/context/me/review-queue/submit`
- `POST /api/v1/context/me/review-queue/submit-bulk`
- `GET /api/v1/context/me/word-progress`
- `GET /api/v1/context/me/review-plan`
- `GET /api/v1/context/me/review-summary`

### Learning graph

- `GET /api/v1/learning-graph/me/interests`
- `PUT /api/v1/learning-graph/me/interests`
- `POST /api/v1/learning-graph/me/semantic-upsert`
- `GET /api/v1/learning-graph/me/recommendations`
- `GET /api/v1/learning-graph/me/anchors`
- `GET /api/v1/learning-graph/me/overview`
- `GET /api/v1/learning-graph/me/observability`

## Проверки и тесты

### Проверка границ модулей

```bash
python tools/check_module_boundaries.py
```

Эта проверка подтверждает, что:

- межмодульные импорты проходят через `public_api` или явные фасады
- `application_service.py` не возвращает response schema из web-слоя

### Тесты

```bash
pytest -q
```

Текущий тестовый контур в основном интеграционный и использует SQLite in-memory.

## Импорт данных

В проекте есть `base_lexicon` seed для быстрого локального перевода частотных слов.

Импорт:

```bash
python tools/import_base_lexicon.py data/base_lexicon.seed.json
```

## Дополнительные материалы

Подробности по слоям, границам модулей и runtime-ограничениям смотри в [ARCHITECTURE.md](/d:/VKR/VKR_V3_Curs/backend/ARCHITECTURE.md).
