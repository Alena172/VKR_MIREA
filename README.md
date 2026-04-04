# ContextVocab

ContextVocab - это full-stack платформа для изучения английского языка русскоязычными пользователями. Проект объединяет:

- backend на FastAPI
- frontend на React
- браузерное расширение для захвата слов со страниц
- PostgreSQL, Redis, Celery и Flower для хранения данных и фоновых задач

Продукт построен вокруг одного практического цикла:

1. найти слово в живом контексте
2. сохранить его вместе с переводом и определением по контексту
3. потренироваться на сохраненной лексике
4. повторить слабые и overdue-слова через SRS

## Структура репозитория

```text
backend/    FastAPI modular monolith, миграции БД, тесты, Celery-задачи
frontend/   React + Vite single-page application
extension/  Browser extension (Manifest V3)
gateway/    Nginx-конфиг для единой локальной точки входа
docs/       Дополнительные заметки по проекту
```

## Быстрый старт

### Полный запуск через Docker

1. Скопируй файл окружения backend:

```bash
cd backend
copy .env.example .env
cd ..
```

2. Подними стек:

```bash
docker compose up -d --build
```

3. Открой сервисы:

- frontend: `http://localhost:5173`
- backend API: `http://localhost:8000`
- gateway: `http://localhost:8080`
- Flower: `http://localhost:5555`

### Режим разработки с live reload

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Этот режим включает:

- autoreload backend через uvicorn
- dev-сервер frontend с отслеживанием изменений
- автоматический запуск миграций при старте backend

## Основные возможности продукта

- JWT-аутентификация с входом или регистрацией в один шаг
- персональный словарь с леммой, переводом, исходным предложением и контекстным определением
- захват слов через браузерное расширение
- перевод EN -> RU на основе гибридной AI/local логики
- асинхронная генерация упражнений
- отправка учебных сессий с проверкой ответов и feedback
- SRS review queue, review plan и review summary
- graph-enhanced сигналы для рекомендаций по уже известным словам

## Текущая модель рекомендаций

Сейчас самый зрелый recommendation-flow в проекте связан именно с повторением уже известных слов:

- recent mistakes
- difficult words
- due words по SRS
- дополнительные graph-based boosts

В проекте пока нет отдельного production-ready механизма, который бы полноценно рекомендовал совершенно новые слова из внешнего пула кандидатов.

## Куда читать дальше

- [ARCHITECTURE.md](/d:/VKR/VKR_V3_Curs/ARCHITECTURE.md)
- [backend/README.md](/d:/VKR/VKR_V3_Curs/backend/README.md)
- [backend/ARCHITECTURE.md](/d:/VKR/VKR_V3_Curs/backend/ARCHITECTURE.md)
- [frontend/README.md](/d:/VKR/VKR_V3_Curs/frontend/README.md)
- [extension/README.md](/d:/VKR/VKR_V3_Curs/extension/README.md)
