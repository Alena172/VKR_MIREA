# Архитектурные заметки

## Область системы
Модульный монолит для веб-приложения и браузерного расширения.

Ограничения предметной области:
- Родной язык всегда русский.
- Изучаемый язык всегда английский.
- Языковые поля намеренно не хранятся в профиле пользователя.

## Границы модулей backend
- auth: точка входа для аутентификации и идентификации
- users: пользователи и базовый уровень CEFR
- vocabulary: английская лемма, русский перевод и контекст источника
- capture: прием данных из браузерного расширения
- translation: контекстный перевод EN->RU
- exercise_engine: генерация учебных заданий
- learning_session: отправка ответов, AI-обратная связь по ошибкам и результаты сессии
- context_memory: SRS-логика, очередь повторения, review-plan/review-summary
- ai_services: фасад AI/ML-инференса
- learning_graph: персональный граф обучения (интересы, semantic senses, кластеры, ошибки)
- tasks: polling статуса фоновых задач Celery

## Правила интеграции
- Модули взаимодействуют через явные сервисные интерфейсы или API-контракты.
- Прямой доступ к таблицам другого модуля запрещен.
- Использование AI централизовано в `ai_services`.
- Эндпоинты, привязанные к пользователю, требуют JWT (`Authorization: Bearer`).
- При несовпадении `user_id` и токена возвращается HTTP 403, при отсутствии/невалидности токена HTTP 401.
- Для новых клиентских сценариев используются `me`-маршруты без явного `user_id`.

### Импортные границы модулей
- Внешний модуль может зависеть от другого backend-модуля только через `public_api` или через экспортированный фасад в `__init__.py`.
- Импорт `repository`, `application_service` и `models` чужого модуля считается нарушением архитектурной границы.
- Импорт этих слоев внутри собственного модуля разрешен.
- Общие платформенные компоненты (`app.core.*`) не относятся к модульным границам и могут использоваться всеми модулями.
- Межмодульный `public_api` должен возвращать DTO из `contracts.py`, а не ORM-модели или HTTP response-схемы.
- Преобразование внутренних моделей в DTO выполняется в `assembler.py`.

Примеры:
- корректно: `from app.modules.learning_graph.public_api import learning_graph_public_api`
- корректно: `from app.modules.learning_graph import learning_graph_public_api`
- некорректно: `from app.modules.learning_graph.repository import learning_graph_repository`
- некорректно: `from app.modules.context_memory.application_service import context_memory_application_service`
- корректно: `translation.application_service -> TranslationResultDTO -> translation.router -> TranslateResponse`
- некорректно: `translation.application_service -> TranslateResponse`

Для автоматической проверки используется команда:

```bash
python tools/check_module_boundaries.py
```

Этот checker валидирует две вещи:
- cross-module импорты не обходят `public_api`;
- `application_service.py` не возвращает и не конструирует web response-схемы своего модуля.

### Стандарт внутренних слоев
- `repository.py` отвечает только за persistence и SQLAlchemy.
- `application_service.py`/`submission_service.py` оркестрируют use-case и не должны зависеть от web-слоя.
- `contracts.py` содержит DTO для межмодульных и внутренних application-result контрактов.
- `assembler.py` содержит явные преобразования `model/result -> DTO`.
- `router.py` преобразует application DTO в HTTP response schema.

## Состояние слоя данных
Персистентные модули (SQLAlchemy):
- users
- vocabulary
- capture
- context_memory
- learning_sessions
- learning_session_answers
- learning_graph_* (interests, topic_clusters, word_senses, relations, mistake_events, links)

AI-сценарии (текущий локальный stub-провайдер):
- translation
- exercise_engine
- объяснения ошибок в learning_session
- ai_services

Провайдер AI:
- поддержан режим `stub` (по умолчанию)
- поддержан режим `openai_compatible` с внешним `/chat/completions`
- есть endpoint диагностики `ai/status` для проверки активного режима и параметров

Контур обучения:
- `sessions/submit` сохраняет агрегат сессии и ответы по каждому упражнению
- `sessions/me` и `sessions/me/{session_id}/answers` дают user-scoped доступ к истории без `user_id` в query
- `sessions/me` поддерживает серверные фильтры и пагинацию для масштабирования UI истории
- для неверных ответов генерируется `explanation_ru`
- слово из `prompt` автоматически попадает в `context_memory.difficult_words`
- `context/{user_id}/recommendations` объединяет сложные слова и последние ошибки в список на повторение
- список на повторение ранжируется по частоте и свежести ошибок с бонусом за `difficult_words`
- endpoint рекомендаций также возвращает `scores` для прозрачного объяснения ранжирования
- SRS-прогресс хранится в `word_progress` (`correct_streak`, `next_review_at`) и обновляется при каждом ответе
- `context/{user_id}/review-queue` возвращает очередь слов, уже готовых к повторению по SRS
- `context/{user_id}/review-queue/submit` позволяет обновлять SRS по одному слову вне полной сессии
- `context/{user_id}/review-queue/submit-bulk` позволяет обновлять SRS пачкой для снижения числа запросов с фронта
- `context/{user_id}/word-progress` и `context/{user_id}/word-progress/{word}` дают доступ к состоянию SRS для UI прогресса
- `context/{user_id}/word-progress/{word}` (`DELETE`) удаляет SRS-запись слова и очищает его из `difficult_words`
- `context/{user_id}/word-progress` поддерживает фильтры `status` и `q` для экранов due/mastered/troubled
- `context/{user_id}/word-progress` также поддерживает серверную сортировку (`sort_by`, `sort_order`)
- пороги для `mastered/troubled` задаются через query-параметры (`min_streak`, `min_errors`)
- `context/{user_id}/review-plan` отдает единый ответ для экрана повторения с настраиваемым горизонтом (due/upcoming/recommended)
- `context/review-summary` агрегирует состояние SRS (due/mastered/troubled) для дашборда
- `vocabulary/from-capture` объединяет capture/translation/vocabulary/SRS-init в одном endpoint
- `vocabulary/from-capture` также синхронизирует `learning_graph.word_senses` и связь с `vocabulary_items`
- `learning_graph/me/interests` позволяет управлять интересами пользователя как сигналом рекомендаций
- `learning_graph/me/semantic-upsert` обеспечивает семантическую дедупликацию (lemma + semantic_key)
- `learning_graph/me/recommendations` отдает рекомендации в режимах `interest|weakness|mixed`
- `learning_graph/me/recommendations` возвращает `strategy_sources[]` и `primary_strategy` для explainability в UI
- `learning_graph/me/anchors` возвращает anchor-узлы для конкретной леммы (связи/веса/типы)
- `learning_graph/me/observability` возвращает quality-метрики выдачи и латентности стратегий
- `learning_graph/me/overview` дает агрегированную картину графа (узлы/ребра/топ-кластеры/теги ошибок)
- `vocabulary/me/from-capture` и `capture/me` дают тот же сценарий через user-scoped JWT-маршруты
- `translate/me` и `exercises/me/generate` фиксируют AI-сценарии без явного `user_id` в клиентских payload
- `auth/token`, `auth/verify` и `auth/me` закрывают JWT-аутентификацию и идентификацию пользователя
- браузерное расширение работает как внешний клиент к `translate` и `study-flow`

## Стратегия миграций
- Схема БД управляется через Alembic.
- Начальная миграция: `alembic/versions/0001_initial_schema.py`.



