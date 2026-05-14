# Схема базы данных

## Текущая продуктовая модель

Практическая схема БД выстроена вокруг реального пользовательского цикла:

1. пользователь существует в `users`
2. слово или фраза попадает в `user_vocabulary`
3. для слов запись опирается на общий словарь `dictionary_entries`
4. слой `review` хранит состояние повторения в `word_progress`
5. учебные попытки фиксируются в `learning_sessions` и `learning_session_answers`
6. модуль `graph` хранит пользовательские интересы, а также общий семантический граф смыслов и связей

Основные сущности:

- `users`
- `dictionary_entries`
- `user_vocabulary`
- `word_progress`
- `learning_sessions`
- `learning_session_answers`
- `user_interests`
- `topic_clusters`
- `word_senses`
- `vocabulary_sense_links`
- `sense_relations`
- `sense_error_events`

## Что важно в текущей схеме

### 1. Словарь нормализован

Словарный слой разделен на:

- `dictionary_entries` — общий словарь смыслов
- `user_vocabulary` — личный словарь пользователя

Это позволяет переиспользовать один и тот же словарный entry между несколькими пользователями без дублирования строк.

### 2. `user_vocabulary` хранит и слова, и фразы

Таблица работает в двух режимах:

- слово: `entry_id` заполнен, `phrase_en` и `phrase_ru` пустые
- фраза: `entry_id` пустой, `phrase_en` и `phrase_ru` заполнены

Из-за этого `entry_id` является nullable, а в таблице есть check-ограничение, запрещающее полностью пустую запись.

### 3. `word_progress` привязан к записи словаря

Повторение больше не живет только на уровне строки `word`. Основной ключ для карточки повторения теперь:

- `(user_id, vocabulary_id)` — одна запись прогресса на одну пользовательскую словарную запись

Поле `word` больше не хранится. Источник истины для карточки повторения теперь только `vocabulary_id`, а сама связь обязательна (`NOT NULL`).

### 4. SRS хранит факты, а не статусы

`word_progress` хранит:

- `error_count`
- `correct_streak`
- `ease_factor`
- `interval_days`
- `last_reviewed_at`
- `next_review_at`

Статусы вроде `due`, `mastered` и `troubled` вычисляются на уровне приложения.

### 5. Семантический граф отделен от пользовательского слоя

Модуль `graph` хранит:

- интересы пользователя в `user_interests`
- общие тематические кластеры в `topic_clusters`
- общие смыслы слов в `word_senses`
- привязку пользовательских словарных записей к общим смыслам в `vocabulary_sense_links`
- общие связи между смыслами в `sense_relations`
- след ошибок на уровне смысла в `sense_error_events`

После денормализации:

- `topic_clusters` больше не содержит `user_id`
- `word_senses` больше не содержит `user_id`, `source_sentence`, `source_url`
- `vocabulary_sense_links` больше не содержит `user_id`
- `sense_relations` больше не содержит `user_id`

Это значит, что учебная логика и семантическая логика остаются связанными, но общий граф смыслов больше не дублируется по пользователям.

### 6. Важные `ON DELETE`-правила

Текущая схема опирается на следующие правила:

- удаление `user_vocabulary` каскадно удаляет связанные строки `word_progress`
- удаление `user_vocabulary` каскадно удаляет `vocabulary_sense_links`
- удаление `word_senses` каскадно удаляет `vocabulary_sense_links`
- удаление `word_senses` каскадно удаляет `sense_relations`
- удаление `learning_sessions` выставляет `sense_error_events.session_id = NULL`
- удаление `word_senses` выставляет `sense_error_events.word_sense_id = NULL`

## Уникальные ограничения

| Таблица | Constraint | Поля |
|---|---|---|
| `users` | UK | `email` |
| `dictionary_entries` | UK | `(english_lemma, russian_translation)` |
| `user_vocabulary` | UK | `(user_id, entry_id)` |
| `user_vocabulary` | UK | `(user_id, phrase_en)` |
| `word_progress` | UK index | `(user_id, vocabulary_id)` |
| `learning_session_answers` | UK | `(session_id, exercise_id)` |
| `user_interests` | UK | `(user_id, interest_key)` |
| `topic_clusters` | UK | `cluster_key` |
| `word_senses` | UK | `(english_lemma, semantic_key)` |
| `vocabulary_sense_links` | UK | `vocabulary_item_id` |
| `sense_relations` | UK | `(left_sense_id, right_sense_id)` |

## Mermaid ER-диаграмма

```mermaid
erDiagram
    users {
        INTEGER id PK
        VARCHAR_320 email UK
        VARCHAR_200 full_name
        VARCHAR_512 password_hash
        VARCHAR_2 cefr_level
        TIMESTAMP created_at
    }

    dictionary_entries {
        INTEGER id PK
        VARCHAR_200 english_lemma
        VARCHAR_200 russian_translation
        TEXT context_definition_ru
        TIMESTAMP created_at
    }

    user_vocabulary {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER entry_id FK
        VARCHAR_500 phrase_en
        VARCHAR_500 phrase_ru
        TEXT source_sentence
        VARCHAR_2000 source_url
        TIMESTAMP added_at
    }

    word_progress {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER vocabulary_id FK
        INTEGER error_count
        INTEGER correct_streak
        FLOAT ease_factor
        INTEGER interval_days
        TIMESTAMP last_reviewed_at
        TIMESTAMP next_review_at
    }

    learning_sessions {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER total
        INTEGER correct
        FLOAT accuracy
        TIMESTAMP created_at
    }

    learning_session_answers {
        INTEGER id PK
        INTEGER session_id FK
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
        INTEGER id PK
        INTEGER user_id FK
        VARCHAR_64 interest_key
        VARCHAR_120 display_name
        FLOAT weight
        TIMESTAMP created_at
    }

    topic_clusters {
        INTEGER id PK
        VARCHAR_64 cluster_key
        VARCHAR_120 name
        TIMESTAMP created_at
    }

    word_senses {
        INTEGER id PK
        VARCHAR_200 english_lemma
        VARCHAR_120 semantic_key
        VARCHAR_200 russian_translation
        TEXT context_definition_ru
        INTEGER topic_cluster_id FK
        TIMESTAMP created_at
    }

    vocabulary_sense_links {
        INTEGER id PK
        INTEGER vocabulary_item_id FK
        INTEGER word_sense_id FK
        TIMESTAMP created_at
    }

    sense_relations {
        INTEGER id PK
        INTEGER left_sense_id FK
        INTEGER right_sense_id FK
        VARCHAR_64 relation_type
        FLOAT score
        TIMESTAMP created_at
    }

    sense_error_events {
        INTEGER id PK
        INTEGER user_id FK
        INTEGER session_id FK
        VARCHAR_200 english_lemma
        INTEGER word_sense_id FK
        VARCHAR_120 mistake_tag
        TEXT prompt
        VARCHAR_1000 expected_answer
        VARCHAR_1000 user_answer
        TIMESTAMP created_at
    }

    users ||--o{ user_vocabulary : владеет
    users ||--o{ word_progress : отслеживает
    users ||--o{ learning_sessions : владеет
    users ||--o{ user_interests : имеет
    users ||--o{ sense_error_events : имеет

    dictionary_entries ||--o{ user_vocabulary : словарная_основа
    user_vocabulary ||--o{ word_progress : прогресс_по_записи
    learning_sessions ||--o{ learning_session_answers : содержит_ответы
    topic_clusters ||--o{ word_senses : объединяет_смыслы
    user_vocabulary ||--o{ vocabulary_sense_links : связывает_со_смыслом
    word_senses ||--o{ vocabulary_sense_links : связан_со_словарем
    word_senses ||--o{ sense_relations : левая_связь
    word_senses ||--o{ sense_relations : правая_связь
    learning_sessions ||--o{ sense_error_events : источник_ошибки
    word_senses ||--o{ sense_error_events : привязка_к_смыслу
```

## Комментарий для защиты

Если показывать схему на защите, удобнее объяснять ее не по таблицам, а по трем слоям:

- словарь: `dictionary_entries`, `user_vocabulary`
- повторение: `word_progress`, `learning_sessions`, `learning_session_answers`
- семантический профиль и граф: `user_interests`, `topic_clusters`, `word_senses`, `vocabulary_sense_links`, `sense_relations`, `sense_error_events`

Так схема выглядит проще и лучше отражает реальные пользовательские сценарии.
