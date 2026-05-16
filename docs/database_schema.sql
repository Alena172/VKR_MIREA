CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    full_name VARCHAR(200),
    password_hash VARCHAR(512),
    cefr_level VARCHAR(2) NOT NULL DEFAULT 'A1',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_users_email ON users(email);

CREATE TABLE topic_clusters (
    id SERIAL PRIMARY KEY,
    cluster_key VARCHAR(64) NOT NULL,
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_topic_cluster_key UNIQUE (cluster_key)
);

CREATE INDEX ix_topic_clusters_cluster_key ON topic_clusters(cluster_key);

CREATE TABLE dictionary_entries (
    id SERIAL PRIMARY KEY,
    english_lemma VARCHAR(200) NOT NULL,
    russian_translation VARCHAR(200) NOT NULL,
    context_definition_ru TEXT,
    topic_cluster_id INTEGER REFERENCES topic_clusters(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dictionary_entry_lemma_translation
        UNIQUE (english_lemma, russian_translation)
);

CREATE INDEX ix_dictionary_entries_english_lemma ON dictionary_entries(english_lemma);
CREATE INDEX ix_dictionary_entries_topic_cluster_id ON dictionary_entries(topic_cluster_id);

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
    vocabulary_id INTEGER NOT NULL REFERENCES user_vocabulary(id) ON DELETE CASCADE,
    error_count INTEGER NOT NULL DEFAULT 0,
    correct_streak INTEGER NOT NULL DEFAULT 0,
    ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 1,
    last_reviewed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    next_review_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_word_progress_vocabulary ON word_progress(vocabulary_id);
CREATE INDEX ix_word_progress_vocabulary_id ON word_progress(vocabulary_id);
CREATE INDEX ix_word_progress_next_review_at ON word_progress(next_review_at);

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

CREATE INDEX ix_learning_session_answers_session_id ON learning_session_answers(session_id);
CREATE INDEX ix_learning_session_answers_target_word ON learning_session_answers(target_word);

CREATE TABLE user_interests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    interest_key VARCHAR(64) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_interest_key UNIQUE (user_id, interest_key)
);

CREATE INDEX ix_user_interests_user_id ON user_interests(user_id);
CREATE INDEX ix_user_interests_interest_key ON user_interests(interest_key);
