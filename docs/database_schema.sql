-- Актуальный снимок PostgreSQL-схемы для документации.
-- Эта версия отражает текущие ORM-модели и практическую структуру БД.

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    full_name VARCHAR(200),
    password_hash VARCHAR(512),
    cefr_level VARCHAR(2) NOT NULL DEFAULT 'A1',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE dictionary_entries (
    id SERIAL PRIMARY KEY,
    english_lemma VARCHAR(200) NOT NULL,
    russian_translation VARCHAR(200) NOT NULL,
    context_definition_ru TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dictionary_entry_lemma_translation
        UNIQUE (english_lemma, russian_translation)
);

CREATE INDEX ix_dictionary_entries_english_lemma
    ON dictionary_entries(english_lemma);

CREATE TABLE user_vocabulary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    entry_id INTEGER REFERENCES dictionary_entries(id),
    phrase_en VARCHAR(500),
    phrase_ru VARCHAR(500),
    source_sentence TEXT,
    source_url VARCHAR(2000),
    added_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_vocabulary_user_entry UNIQUE (user_id, entry_id),
    CONSTRAINT uq_user_vocabulary_user_phrase UNIQUE (user_id, phrase_en),
    CONSTRAINT ck_user_vocabulary_word_or_phrase
        CHECK ((entry_id IS NOT NULL) OR (phrase_en IS NOT NULL))
);

CREATE INDEX ix_user_vocabulary_user_id ON user_vocabulary(user_id);
CREATE INDEX ix_user_vocabulary_entry_id ON user_vocabulary(entry_id);
CREATE INDEX ix_user_vocabulary_phrase_en ON user_vocabulary(phrase_en);

CREATE TABLE word_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    vocabulary_id INTEGER NOT NULL REFERENCES user_vocabulary(id) ON DELETE CASCADE,
    error_count INTEGER NOT NULL DEFAULT 0,
    correct_streak INTEGER NOT NULL DEFAULT 0,
    ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 1,
    last_reviewed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    next_review_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_word_progress_user_id ON word_progress(user_id);
CREATE INDEX ix_word_progress_vocabulary_id ON word_progress(vocabulary_id);
CREATE INDEX ix_word_progress_next_review_at ON word_progress(next_review_at);
CREATE UNIQUE INDEX uq_word_progress_user_vocabulary
    ON word_progress(user_id, vocabulary_id);

CREATE TABLE learning_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    accuracy DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_learning_sessions_user_id ON learning_sessions(user_id);

CREATE TABLE learning_session_answers (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES learning_sessions(id),
    exercise_id INTEGER NOT NULL,
    exercise_type VARCHAR(64),
    target_word VARCHAR(200),
    prompt TEXT,
    expected_answer VARCHAR(1000),
    user_answer VARCHAR(1000) NOT NULL,
    is_correct BOOLEAN NOT NULL,
    explanation_ru TEXT,
    CONSTRAINT uq_learning_session_answers_session_exercise
        UNIQUE (session_id, exercise_id)
);

CREATE INDEX ix_learning_session_answers_session_id
    ON learning_session_answers(session_id);
CREATE INDEX ix_learning_session_answers_target_word
    ON learning_session_answers(target_word);

CREATE TABLE user_interests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    interest_key VARCHAR(64) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_interest_key UNIQUE (user_id, interest_key)
);

CREATE INDEX ix_user_interests_interest_key ON user_interests(interest_key);

CREATE TABLE topic_clusters (
    id SERIAL PRIMARY KEY,
    cluster_key VARCHAR(64) NOT NULL,
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_topic_cluster_key UNIQUE (cluster_key)
);

CREATE INDEX ix_topic_clusters_cluster_key ON topic_clusters(cluster_key);

CREATE TABLE word_senses (
    id SERIAL PRIMARY KEY,
    english_lemma VARCHAR(200) NOT NULL,
    semantic_key VARCHAR(120) NOT NULL,
    russian_translation VARCHAR(200) NOT NULL,
    context_definition_ru TEXT,
    topic_cluster_id INTEGER REFERENCES topic_clusters(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_word_sense_lemma_key
        UNIQUE (english_lemma, semantic_key)
);

CREATE INDEX ix_word_senses_english_lemma ON word_senses(english_lemma);
CREATE INDEX ix_word_senses_semantic_key ON word_senses(semantic_key);
CREATE INDEX ix_word_senses_topic_cluster_id ON word_senses(topic_cluster_id);

CREATE TABLE vocabulary_sense_links (
    id SERIAL PRIMARY KEY,
    vocabulary_item_id INTEGER NOT NULL REFERENCES user_vocabulary(id) ON DELETE CASCADE,
    word_sense_id INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vocab_sense_link_vocab UNIQUE (vocabulary_item_id)
);

CREATE INDEX ix_vocabulary_sense_links_vocabulary_item_id
    ON vocabulary_sense_links(vocabulary_item_id);
CREATE INDEX ix_vocabulary_sense_links_word_sense_id
    ON vocabulary_sense_links(word_sense_id);

CREATE TABLE sense_relations (
    id SERIAL PRIMARY KEY,
    left_sense_id INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    right_sense_id INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    relation_type VARCHAR(64) NOT NULL DEFAULT 'semantic_overlap',
    score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sense_relation_pair
        UNIQUE (left_sense_id, right_sense_id)
);

CREATE INDEX ix_sense_relations_left_sense_id ON sense_relations(left_sense_id);
CREATE INDEX ix_sense_relations_right_sense_id ON sense_relations(right_sense_id);

CREATE TABLE sense_error_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    session_id INTEGER REFERENCES learning_sessions(id) ON DELETE SET NULL,
    english_lemma VARCHAR(200),
    word_sense_id INTEGER REFERENCES word_senses(id) ON DELETE SET NULL,
    mistake_tag VARCHAR(120) NOT NULL,
    prompt TEXT,
    expected_answer VARCHAR(1000),
    user_answer VARCHAR(1000),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_sense_error_events_user_id ON sense_error_events(user_id);
CREATE INDEX ix_sense_error_events_session_id ON sense_error_events(session_id);
CREATE INDEX ix_sense_error_events_english_lemma ON sense_error_events(english_lemma);
CREATE INDEX ix_sense_error_events_word_sense_id ON sense_error_events(word_sense_id);
CREATE INDEX ix_sense_error_events_mistake_tag ON sense_error_events(mistake_tag);
CREATE INDEX ix_sense_error_events_created_at ON sense_error_events(created_at);
