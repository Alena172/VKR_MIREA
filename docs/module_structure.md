# Структура модулей серверной части

## Цель

Серверная часть устроена как модульный монолит: проект запускается как одно FastAPI-приложение, но бизнес-логика разделена на самостоятельные верхнеуровневые модули.

Чтобы модули читались одинаково, внутри каждого модуля используется единая слоистая структура. В проекте больше не используются вложенные продуктовые подмодули вроде `training/session` или `vocabulary/items`: различия сценариев выражаются именами файлов внутри слоев.

## Модули верхнего уровня

- `identity`: пользователь, авторизация, JWT, профиль и настройки.
- `vocabulary`: личный словарь, перевод, захват слова из контекста, базовый локальный лексикон.
- `training`: генерация упражнений, прохождение сессий, проверка ответов, история.
- `review`: SRS-повторение, очередь повторения, план, сводка прогресса.
- `graph`: семантический профиль пользователя, интересы, смыслы слов и смысловые связи.
- `ai`: фасад к AI-провайдерам, гибридный перевод, генерация определений и упражнений, объяснение ошибок.

## Единый шаблон модуля

```text
module/
  models.py
  repository.py
  router.py
  schemas.py
  service/
    *.py
```

Не каждый модуль обязан иметь все файлы. Файл создается только тогда, когда в нем есть реальная ответственность.

## Назначение слоев

- `router.py`: FastAPI-маршруты, зависимости текущего пользователя, HTTP-схемы запросов и ответов.
- `service/`: пользовательские сценарии, транзакционные границы, координация между репозиторием, внешними адаптерами и другими модулями.
- `repository.py`: запросы к базе данных, работа с SQLAlchemy-сессией.
- `models.py`: SQLAlchemy ORM-модели, описание таблиц.
- `schemas.py`: Pydantic-схемы для запросов, ответов и внутренних DTO.

## Текущая структура

```text
modules/
  identity/
    models.py
    repository.py
    router.py
    schemas.py
    service.py
    deps.py

  vocabulary/
    models.py
    repository.py
    router.py
    schemas.py
    service/
      capture.py
      definition.py
      items.py
      lexicon.py
      translation.py

  training/
    models.py
    repository.py
    router.py
    schemas.py
    service/
      evaluation.py
      exercises.py
      prefetch.py
      submission.py

  review/
    models.py
    repository.py
    router.py
    schemas.py
    service/
      scoring.py
      srs.py

  graph/
    models.py
    repository.py
    router.py
    schemas.py
    service/
      graph.py
      strategies.py

  ai/
    chat_client.py
    facade.py
    router.py
    schemas.py
    service/
      definitions.py
      exercises.py
      translation.py
```

## Правило межмодульных зависимостей

Модуль может обращаться к другому модулю через его сервисы, импортируя только публичные функции из `service/*.py`.

Модуль не обращается напрямую к чужим:

- `repository.py`;
- `models.py`.

Так сохраняется понятная граница: один модуль может менять внутреннюю реализацию, не ломая остальные.

## Итоговое правило

Проект придерживается умеренной слоистости:

```text
HTTP (router.py) -> service/*.py -> repository.py -> models.py
                         |
                         +-> другие модули (через их service/*.py)
                         +-> ai facade (app.modules.ai.facade)
```

Главный ориентир: структура всех модулей выглядит одинаково, а сложность живет в именах файлов, а не в глубокой вложенности папок.
