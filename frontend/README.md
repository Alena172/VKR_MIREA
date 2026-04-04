# Frontend

## Обзор

Frontend - это React + Vite single-page application, через которое пользователь проходит основной цикл ContextVocab:

- регистрируется или входит
- переводит слова и фразы
- сохраняет элементы в словарь
- тренируется на сгенерированных упражнениях
- повторяет due и difficult слова
- просматривает историю сессий

Это основной пользовательский клиент backend API.

## Стек

- React
- Vite
- Tailwind CSS
- React Router

## Локальная разработка

```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

Стандартный адрес dev-сервера:

- `http://localhost:5173`

Ожидаемый backend API:

- `http://localhost:8000/api/v1`

## Переменные окружения

Frontend использует:

- `VITE_API_BASE_URL`: прямой адрес API
- `VITE_DEV_PROXY_TARGET`: optional proxy target для Vite в dev-режиме

См. [`.env.example`](d:\VKR\VKR_V3_Curs\frontend\.env.example).

## Основные экраны

### Home / translate flow

Главный экран является точкой входа для:

- аутентификации
- запросов на перевод
- сохранения слов в словарь

Этот поток тесно связан с backend-модулями `translation` и `vocabulary`.

### Vocabulary

Экран словаря показывает уже сохраненные пользователем элементы.

Для каждого элемента ожидается `context_definition`, соответствующее исходному контексту. На стороне backend это определение сейчас строится по модели `reuse-first, LLM-fallback`.

### Training

Тренировочный поток построен вокруг server-generated exercises.

Важные особенности:

- генерация упражнений может быть асинхронной
- frontend опрашивает статус задачи, если backend возвращает background task
- ответы отправляются в API учебной сессии
- UI показывает generation notes, которые вернул backend

Именно здесь пользователь сильнее всего ощущает AI-assisted генерацию и семантическую проверку ответов.

### Review

Экран повторения ориентирован на уже известные слова, а не на discovery совершенно новой лексики.

Он объединяет:

- due items из системы повторения
- recent mistakes
- difficult words
- дополнительные ranking или boosting сигналы от `learning_graph`

То есть рекомендации здесь отвечают в первую очередь на вопрос "что повторять сейчас", а не "какое новое слово учить дальше".

### Session History

Экран истории показывает прошлые учебные сессии, детали ответов и server-side фильтры, например по дате и accuracy.

## Аутентификация и токены

SPA работает через JWT-аутентификацию backend.

Текущие детали реализации:

- JWT хранится в browser storage
- авторизованные запросы отправляют bearer token
- приложение использует проверки вроде `/auth/verify` и `/auth/me` для восстановления состояния сессии

Для текущего этапа это приемлемо, но это скорее pragmatic implementation detail, чем целевая долгосрочная security-модель.

## Зависимости от backend

Frontend зависит от следующих backend-возможностей:

- auth и user profile
- translation
- vocabulary capture и listing
- exercise generation
- learning session submission
- review planning
- task status polling

Если backend или worker недоступен, это быстрее всего проявится в генерации упражнений, обновлении review-flow и translation-сценариях.

## Замечания по текущему product scope

Текущее состояние frontend честно отражает текущий продукт:

- самый сильный пользовательский путь сейчас: `translate -> capture -> train -> review`
- review-рекомендации заметно зрелее, чем гипотетическая система глобальной рекомендации новых слов
- `learning_graph` показывается как улучшающий слой, а не как главный источник ценности

## Полный запуск full-stack

Из корня репозитория:

```bash
docker compose up -d --build
```

Типичные локальные адреса:

- frontend: `http://localhost:5173`
- backend API: `http://localhost:8000`

## Связанные документы

- [README проекта](d:\VKR\VKR_V3_Curs\README.md)
- [Архитектура проекта](d:\VKR\VKR_V3_Curs\ARCHITECTURE.md)
- [Backend README](d:\VKR\VKR_V3_Curs\backend\README.md)
