# Архитектура

## Обзор системы

Наша система - это платформа для изучения английского языка русскоязычными пользователями через реальный контекст, короткие упражнения и интервальные повторения.

Репозиторий включает:

- backend на FastAPI, построенный как модульный монолит
- frontend на React для словаря, тренировки, повторения и истории
- браузерное расширение для захвата слов с веб-страниц
- Docker Compose-конфигурацию для локального full-stack запуска

Текущий продуктовый цикл выглядит так:

1. Захватить или ввести слово
2. Получить перевод и определение, соответствующее контексту
3. Сохранить слово в личный словарь
4. Потренироваться на сохраненной лексике
5. Повторить слабые и overdue-слова через SRS

## Архитектура в одном взгляде

```text
Browser Extension ----\
                        \
React Frontend ----------> FastAPI backend ----> PostgreSQL
                        /           |            Redis
Other API clients -----/            |
                                     +--> Celery worker / Flower
                                     |
                                     +--> AI provider facade
```

## Основные домены backend

- `auth`: выпуск и проверка JWT
- `users`: профиль пользователя и уровень CEFR
- `vocabulary`: сохраненные леммы, переводы, контекстные определения, capture flow
- `capture`: история захваченного текста из расширения
- `translation`: перевод EN -> RU для текущего пользователя
- `exercise_engine`: генерация упражнений и async exercise jobs
- `learning_session`: отправка ответов, проверка корректности, feedback
- `context_memory`: SRS, review queue, review plan, review summary
- `learning_graph`: интересы, semantic senses, anchors, graph-based signals
- `ai_services`: централизованный AI facade и fallback logic
- `tasks`: polling статуса фоновых задач

## Важные архитектурные решения

### 1. Модульный монолит

Backend специально не разделен на микросервисы.

Границы модулей поддерживаются через:

- `public_api.py` для межмодульного доступа
- `contracts.py` для DTO
- `assembler.py` для преобразования `model -> DTO`
- проверку границ модулей в `backend/tools/check_module_boundaries.py`

Прямые импорты чужих `repository`, `models` или `application_service` считаются архитектурным нарушением.

### 2. AI используется централизованно и гибридно

Все AI-сценарии проходят через `app.modules.ai_services`.

Платформа не опирается на LLM для каждой языковой операции. Текущее поведение гибридное:

- локальные эвристики и `base_lexicon` обрабатывают простые случаи перевода
- внешний AI подключается там, где действительно нужна семантическая неоднозначность или генерация контента
- для перевода и генерации упражнений существуют fallback-пути

Для `context_definition` словарь теперь использует стратегию `reuse-first, LLM-fallback`:

- сначала система пытается переиспользовать уже существующее определение для той же леммы
- если надежного кандидата нет, вызывается AI
- вместе с определением сохраняются метаданные об источнике, confidence и reuse

### 3. Основной recommendation-flow построен вокруг SRS

Сейчас главный recommendation-сценарий в проекте связан не с поиском новых слов, а с тем, какие уже известные слова нужно повторять сейчас.

Рекомендации `context_memory` строятся из:

- recent mistakes
- difficult words
- due words
- дополнительных boost-сигналов от `learning_graph`

Именно этот поток сейчас наиболее важен для продукта.

### 4. Learning graph - это надстройка, а не ядро продукта

`learning_graph` в проекте существует и работает, но на текущем этапе его правильнее считать вторичным слоем улучшения.

Он добавляет:

- хранение интересов пользователя
- semantic sense upsert
- anchor-связи между senses
- graph-based recommendation signals
- observability для recommendation strategies

Но базовый продуктовый цикл должен оставаться ценным и без дальнейшего разрастания этого слоя.

## Runtime-компоненты

### Backend

- FastAPI-приложение в `backend/app/main.py`
- SQLAlchemy ORM и Alembic-миграции
- синхронная модель работы с DB session
- настройка CORS и trusted hosts через settings

### База данных

- PostgreSQL - основное постоянное хранилище
- таблицы организованы по backend-модулям
- Alembic-миграции находятся в `backend/alembic/versions`

### Фоновые задачи

- Celery worker выполняет тяжелые операции
- Redis используется как broker и result backend
- Flower дает мониторинг worker'а
- для отдельных dev-сценариев существует local fallback

### Frontend

- React + Vite + Tailwind
- состояние аутентификации хранится в browser storage
- основные экраны: home, vocabulary, training, review, history

### Extension

- браузерное расширение на Manifest V3
- читает выделенный текст с активной страницы
- вызывает `/translate/me` и `/vocabulary/me/from-capture`

## Ключевые пользовательские потоки

### Захват слова в словарь

1. Пользователь выделяет текст в браузере
2. Расширение отправляет выделение и исходное предложение
3. Backend переводит лемму
4. Backend получает определение, соответствующее контексту
5. Элемент словаря создается или переиспользуется
6. Инициализируется SRS-прогресс
7. Синхронизируются semantic-данные для learning graph

### Тренировка

1. Frontend запрашивает генерацию упражнений
2. Backend ставит задачу в очередь
3. Frontend опрашивает `/tasks/{task_id}`
4. Сгенерированные упражнения показываются в UI
5. Пользователь отправляет ответы
6. Backend проверяет ответы и сохраняет сессию

### Повторение

1. Frontend загружает review summary и review plan
2. Backend строит очередь из due и upcoming слов
3. Recommendation scoring поднимает приоритет известных слабых слов
4. Пользователь проходит SRS или random review session
5. После каждого ответа обновляется прогресс слова

## Карта документации

- [README.md](/d:/VKR/VKR_V3_Curs/README.md): обзор проекта и быстрый старт
- [backend/README.md](/d:/VKR/VKR_V3_Curs/backend/README.md): запуск и эксплуатация backend
- [backend/ARCHITECTURE.md](/d:/VKR/VKR_V3_Curs/backend/ARCHITECTURE.md): границы backend-модулей и технические ограничения
- [frontend/README.md](/d:/VKR/VKR_V3_Curs/frontend/README.md): запуск frontend и текущее состояние UI
- [extension/README.md](/d:/VKR/VKR_V3_Curs/extension/README.md): настройка браузерного расширения
