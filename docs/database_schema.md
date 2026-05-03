# Схема базы данных

## Текущая упрощенная модель

Практическая схема БД приведена к основному продуктовому циклу: пользователь сохраняет слово, система определяет его смысл, формирует упражнения и обновляет прогресс повторения.

Основные сущности:

- `users`
- `base_lexicon_entries`
- `vocabulary_items`
- `word_progress`
- `learning_sessions`
- `learning_session_answers`
- `sense_error_events` как trace ошибок на уровне смысла слова

Семантическое обогащение:

- `user_interests`
- `topic_clusters`
- `word_senses`
- `vocabulary_sense_links`
- `sense_relations`

## Основные упрощения

### 1. Захват слова стал частью vocabulary flow

Выделенный текст сразу обрабатывается внутри сценария словаря. Основной бизнес-сущностью остается `vocabulary_items`.

### 2. `learning_session_answers` хранит структурированные метаданные упражнения

Таблица хранит:

- `exercise_id`
- `exercise_type`
- `target_word`
- `prompt`
- `expected_answer`
- `user_answer`
- `is_correct`
- `explanation_ru`

Благодаря этому система понимает тип упражнения и целевое слово по явным полям.

### 3. Review использует один источник состояния

Слой повторения хранит состояние в `word_progress`. Данные профиля пользователя, например CEFR, остаются в `users`, а факты повторения остаются в `word_progress`.

### 4. Review хранит факты, а статусы вычисляются

Текущий review-слой хранит фактические значения:

- `error_count`
- `correct_streak`
- `last_reviewed_at`
- `next_review_at`

Статусы `due`, `mastered` и `troubled` вычисляются в application logic и UI.

### 5. `learning_graph` формирует semantic profile пользователя

Семантический модуль хранит интересы, смыслы слов, связи словаря со смыслами и связи между смыслами. Его публичный API покрывает пользовательский поток:

- интересы
- semantic upsert
- слова из профиля интересов
- anchors

### 6. `context_memory` сфокусирован на повторении

Публичная часть модуля покрывает:

- review queue
- запуск review session
- обновление прогресса повторения
- список word progress
- review plan
- progress snapshot
- review summary

## Почему эта версия лучше подходит для диплома

Упрощенная схема сохраняет ключевые возможности проекта:

- персональный словарь с контекстными определениями
- учебные сессии с историей ответов
- интервальные повторения на основе результатов пользователя
- AI-assisted генерацию упражнений и feedback
- semantic profile через `learning_graph`

При этом схема остается ближе к демонстрируемому пользовательскому циклу и проще объясняется на защите.

## Mermaid ER-диаграмма

```mermaid
erDiagram
    users {
        BIGINT id PK
        VARCHAR_320 email UK
        VARCHAR_200 full_name
        VARCHAR_2 cefr_level
        TIMESTAMP created_at
    }

    base_lexicon_entries {
        BIGINT id PK
        VARCHAR_200 english_lemma UK
        VARCHAR_200 russian_translation
        TIMESTAMP created_at
    }

    vocabulary_items {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR_200 english_lemma
        VARCHAR_200 russian_translation
        TEXT context_definition_ru
        VARCHAR_64 context_definition_source
        VARCHAR_16 context_definition_confidence
        BIGINT definition_reused_from_item_id
        TEXT source_sentence
        VARCHAR_2000 source_url
    }

    word_progress {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR_200 word
        INTEGER error_count
        INTEGER correct_streak
        TIMESTAMP last_reviewed_at
        TIMESTAMP next_review_at
    }

    learning_sessions {
        BIGINT id PK
        BIGINT user_id FK
        INTEGER total
        INTEGER correct
        FLOAT accuracy
        TIMESTAMP created_at
    }

    learning_session_answers {
        BIGINT id PK
        BIGINT session_id FK
        INTEGER exercise_id
        VARCHAR_64 exercise_type
        VARCHAR_200 target_word
        TEXT prompt
        VARCHAR_1000 expected_answer
        VARCHAR_1000 user_answer
        BOOLEAN is_correct
        TEXT explanation_ru
    }

    user_interests {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR_64 interest_key
        VARCHAR_120 display_name
        FLOAT weight
        TIMESTAMP created_at
    }

    topic_clusters {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR_64 cluster_key
        VARCHAR_120 name
        TEXT description
        TIMESTAMP created_at
    }

    word_senses {
        BIGINT id PK
        BIGINT user_id FK
        VARCHAR_200 english_lemma
        VARCHAR_120 semantic_key
        VARCHAR_200 russian_translation
        TEXT context_definition_ru
        TEXT source_sentence
        VARCHAR_2000 source_url
        BIGINT topic_cluster_id FK
        TIMESTAMP created_at
    }

    vocabulary_sense_links {
        BIGINT id PK
        BIGINT user_id FK
        BIGINT vocabulary_item_id FK
        BIGINT word_sense_id FK
        TIMESTAMP created_at
    }

    sense_relations {
        BIGINT id PK
        BIGINT user_id FK
        BIGINT left_sense_id FK
        BIGINT right_sense_id FK
        VARCHAR_64 relation_type
        FLOAT score
        TIMESTAMP created_at
    }

    sense_error_events {
        BIGINT id PK
        BIGINT user_id FK
        BIGINT session_id FK
        VARCHAR_200 english_lemma
        BIGINT word_sense_id FK
        VARCHAR_120 mistake_tag
        TEXT prompt
        VARCHAR_1000 expected_answer
        VARCHAR_1000 user_answer
        TIMESTAMP created_at
    }

    users ||--o{ vocabulary_items : owns
    users ||--o{ word_progress : tracks
    users ||--o{ learning_sessions : owns
    users ||--o{ user_interests : has
    users ||--o{ topic_clusters : has
    users ||--o{ word_senses : has
    users ||--o{ vocabulary_sense_links : has
    users ||--o{ sense_relations : has
    users ||--o{ sense_error_events : has

    learning_sessions ||--o{ learning_session_answers : contains
    topic_clusters ||--o{ word_senses : groups
    vocabulary_items ||--o{ vocabulary_sense_links : maps
    word_senses ||--o{ vocabulary_sense_links : maps
    word_senses ||--o{ sense_relations : left_side
    word_senses ||--o{ sense_relations : right_side
    learning_sessions ||--o{ sense_error_events : records
    word_senses ||--o{ sense_error_events : classifies
```
