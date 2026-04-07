# Database Schema

## Current simplified model

After the simplification pass, the practical schema is intentionally closer to the real product loop and less overloaded with future-facing links.

Core entities:
- `users`
- `base_lexicon_entries`
- `vocabulary_items`
- `word_progress`
- `learning_sessions`
- `learning_session_answers`
- `mistake_events`

Semantic enrichment:
- `user_interests`
- `topic_clusters`
- `word_senses`
- `vocabulary_sense_links`
- `sense_relations`

## Main simplifications

### 1. Capture is now an internal step of the vocabulary flow

Selected text is processed immediately inside the vocabulary scenario and is no longer persisted as a standalone table. The main business entity remains `vocabulary_items`.

### 2. `learning_session_answers` stores structured exercise metadata

The table keeps:
- `exercise_id`
- `exercise_type`
- `target_word`
- `prompt`
- `expected_answer`
- `user_answer`
- `is_correct`
- `explanation_ru`

This removes the previous dependence on parsing `prompt` text to understand what kind of exercise was shown and which word it was about.

### 3. Review uses one source of truth

The review layer now uses only `word_progress` as its state storage. User profile data such as CEFR remains in `users`, and review-specific facts remain in `word_progress`.

### 4. Review keeps facts, not derived states

The current review layer uses `word_progress` and stores only factual values:
- `error_count`
- `correct_streak`
- `last_reviewed_at`
- `next_review_at`

Statuses such as "due", "mastered" or "troubled" are derived from these fields in application logic and UI. They are not stored separately.

### 5. `learning_graph` is preserved as an enrichment layer

The semantic module still stores interests, senses, sense links and relations, but its public API was reduced to the parts that affect the user flow:
- interests
- semantic upsert
- recommendations
- anchors

Auxiliary observability endpoints were removed from the public surface.

### 6. `context_memory` is focused on review flow

The public part of the module now focuses on:
- review queue
- review session start
- review progress updates
- word progress listing
- review plan
- progress snapshot
- review summary

Cleanup and secondary context-management scenarios are no longer part of the main public flow.

## Why this version is better

The simplified schema still remains strong enough for the graduation project because it preserves:
- personal vocabulary storage with contextual definitions;
- learning sessions with answer history;
- spaced repetition based on user performance;
- AI-supported exercise generation and feedback;
- semantic enrichment through the learning graph.

At the same time, it removes several sources of accidental complexity:
- prompt-based heuristics instead of structured metadata;
- public endpoints that were useful mainly for debugging or compensation;
- review fields that can be derived instead of stored;
- excessive emphasis on capture as a standalone product module.

## Mermaid ER diagram

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

    mistake_events {
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
    users ||--o{ mistake_events : has

    learning_sessions ||--o{ learning_session_answers : contains
    topic_clusters ||--o{ word_senses : groups
    vocabulary_items ||--o{ vocabulary_sense_links : maps
    word_senses ||--o{ vocabulary_sense_links : maps
    word_senses ||--o{ sense_relations : left_side
    word_senses ||--o{ sense_relations : right_side
    learning_sessions ||--o{ mistake_events : records
    word_senses ||--o{ mistake_events : classifies
```
