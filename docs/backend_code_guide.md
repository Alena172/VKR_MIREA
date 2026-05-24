# Backend Code Guide

Этот файл помогает быстро сориентироваться в серверной части без долгого чтения всего дерева `backend/app`.

## С чего начать

- `backend/app/main.py` — точка входа FastAPI, middleware, healthcheck и startup-логика.
- `backend/app/core/api.py` — собирает все доменные роутеры в единое API `/api/v1`.
- `backend/app/celery_app.py` — настройка Celery и локальный fallback, если worker недоступен.
- `backend/app/core/db.py` — SQLAlchemy engine, `SessionLocal`, dependency `get_db()` и транзакционный helper.

## Как устроен backend

- `core/` — инфраструктурный слой приложения: конфиг, БД, API-композиция и общие helper-объекты.
- `modules/identity/` — регистрация, логин, JWT и профиль текущего пользователя.
- `modules/vocabulary/` — личный словарь, захват слов со страницы, перевод и смена смысла слова.
- `modules/training/` — генерация упражнений, prefetch-буфер и история учебных сессий.
- `modules/review/` — интервальное повторение, очередь review и агрегаты прогресса.
- `modules/graph/` — граф интересов и тематические подсказки для новых слов.
- `tasks/` — фоновые Celery-задачи, которые повторно используют сервисный слой модулей.
- `platform/tasks/` — API для polling статуса фоновых задач.

## Как читать запрос от API до БД

1. Открыть `router.py` нужного модуля.
2. Перейти в соответствующий `service.py` или `service/*`.
3. Найти вызовы `repository.py`, если нужно понять SQLAlchemy-запросы и сохранение данных.
4. Проверить `schemas.py`, чтобы увидеть форму входа и ответа для API и подсказки, которые попадут в Swagger.
5. Если сценарий асинхронный, дополнительно посмотреть `backend/app/tasks/*.py`.

## Что смотреть в Swagger

- Описания эндпоинтов берутся из докстрингов функций в `router.py`.
- Формы запросов и ответов берутся из `schemas.py`.
- Группировка по разделам зависит от `tags` у `APIRouter`.
- Если описание в Swagger выглядит бедно, почти всегда править нужно `router.py` или `schemas.py`.

## Полезные маршруты чтения

- Аутентификация: `modules/identity/router.py` → `modules/identity/service.py` → `modules/identity/repository.py`
- Добавление слова: `modules/vocabulary/router.py` → `modules/vocabulary/service/items.py`
- Генерация упражнений: `modules/training/router.py` → `modules/training/service/exercises.py` → `tasks/exercise_tasks.py`
- Повторение слов: `modules/review/router.py` → `modules/review/service/srs.py`
- AI-перевод и генерация: `modules/ai/facade.py` → `modules/ai/service/*`
- Граф интересов: `modules/graph/router.py` → `modules/graph/service/graph.py`

## Что важно помнить

- Большая часть бизнес-логики живёт в сервисах, а роутеры стараются быть тонкими.
- Многие фоновые задачи используют те же сервисы, что и HTTP-эндпоинты, поэтому поведение обычно совпадает.
- Докстринги на роутерах попадают в Swagger, поэтому короткие описания эндпоинтов лучше искать именно там.
- Самые сложные эвристики сейчас сосредоточены в `modules/ai/service/*`, `modules/review/service/srs.py` и `modules/graph/repository.py`.
