-- Practical database schema aligned with the current simplified implementation.
-- Capture is handled inside the vocabulary flow, review stores only factual progress,
-- and learning session answers keep structured exercise metadata instead of
-- recovering behavior from prompt text.

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    full_name VARCHAR(200),
    cefr_level VARCHAR(2) NOT NULL DEFAULT 'A1',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE base_lexicon_entries (
    id SERIAL PRIMARY KEY,
    english_lemma VARCHAR(200) NOT NULL UNIQUE,
    russian_translation VARCHAR(200) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE vocabulary_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    english_lemma VARCHAR(200) NOT NULL,
    russian_translation VARCHAR(200) NOT NULL,
    context_definition_ru TEXT,
    context_definition_source VARCHAR(64),
    context_definition_confidence VARCHAR(16),
    definition_reused_from_item_id INTEGER,
    source_sentence TEXT,
    source_url VARCHAR(2000)
);

ALTER TABLE vocabulary_items
    ADD CONSTRAINT fk_vocabulary_definition_reused_from_item
    FOREIGN KEY (definition_reused_from_item_id)
    REFERENCES vocabulary_items(id)
    ON DELETE SET NULL;

CREATE INDEX ix_vocabulary_items_user_id ON vocabulary_items(user_id);
CREATE INDEX ix_vocabulary_items_english_lemma ON vocabulary_items(english_lemma);
CREATE INDEX ix_vocabulary_items_definition_reused_from_item_id ON vocabulary_items(definition_reused_from_item_id);

CREATE TABLE word_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    word VARCHAR(200) NOT NULL,
    error_count INTEGER NOT NULL DEFAULT 0,
    correct_streak INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    next_review_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_word_progress_user_word UNIQUE (user_id, word)
);

CREATE INDEX ix_word_progress_user_id ON word_progress(user_id);
CREATE INDEX ix_word_progress_word ON word_progress(word);
CREATE INDEX ix_word_progress_next_review_at ON word_progress(next_review_at);

CREATE TABLE learning_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    total INTEGER NOT NULL CHECK (total >= 0),
    correct INTEGER NOT NULL CHECK (correct >= 0 AND correct <= total),
    accuracy DOUBLE PRECISION NOT NULL CHECK (accuracy >= 0 AND accuracy <= 1),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

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
    explanation_ru TEXT
);

CREATE INDEX ix_learning_session_answers_session_id ON learning_session_answers(session_id);
CREATE INDEX ix_learning_session_answers_target_word ON learning_session_answers(target_word);
CREATE UNIQUE INDEX uq_learning_session_answers_session_exercise
    ON learning_session_answers(session_id, exercise_id);

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
    user_id INTEGER NOT NULL REFERENCES users(id),
    cluster_key VARCHAR(64) NOT NULL,
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_topic_cluster_user_key UNIQUE (user_id, cluster_key)
);
CREATE INDEX ix_topic_clusters_cluster_key ON topic_clusters(cluster_key);

CREATE TABLE word_senses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    english_lemma VARCHAR(200) NOT NULL,
    semantic_key VARCHAR(120) NOT NULL,
    russian_translation VARCHAR(200) NOT NULL,
    context_definition_ru TEXT,
    source_sentence TEXT,
    source_url VARCHAR(2000),
    topic_cluster_id INTEGER REFERENCES topic_clusters(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_word_sense_user_lemma_key UNIQUE (user_id, english_lemma, semantic_key)
);

CREATE INDEX ix_word_senses_user_id ON word_senses(user_id);
CREATE INDEX ix_word_senses_english_lemma ON word_senses(english_lemma);
CREATE INDEX ix_word_senses_semantic_key ON word_senses(semantic_key);
CREATE INDEX ix_word_senses_topic_cluster_id ON word_senses(topic_cluster_id);

CREATE TABLE vocabulary_sense_links (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    vocabulary_item_id INTEGER NOT NULL REFERENCES vocabulary_items(id),
    word_sense_id INTEGER NOT NULL REFERENCES word_senses(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vocab_sense_link_user_vocab UNIQUE (user_id, vocabulary_item_id)
);

CREATE INDEX ix_vocabulary_sense_links_user_id ON vocabulary_sense_links(user_id);
CREATE INDEX ix_vocabulary_sense_links_vocabulary_item_id ON vocabulary_sense_links(vocabulary_item_id);
CREATE INDEX ix_vocabulary_sense_links_word_sense_id ON vocabulary_sense_links(word_sense_id);

CREATE TABLE sense_relations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    left_sense_id INTEGER NOT NULL REFERENCES word_senses(id),
    right_sense_id INTEGER NOT NULL REFERENCES word_senses(id),
    relation_type VARCHAR(64) NOT NULL DEFAULT 'semantic_overlap',
    score DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (score >= 0 AND score <= 1),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sense_relation_pair UNIQUE (user_id, left_sense_id, right_sense_id)
);

CREATE INDEX ix_sense_relations_user_id ON sense_relations(user_id);
CREATE INDEX ix_sense_relations_left_sense_id ON sense_relations(left_sense_id);
CREATE INDEX ix_sense_relations_right_sense_id ON sense_relations(right_sense_id);

CREATE TABLE mistake_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    session_id INTEGER REFERENCES learning_sessions(id),
    english_lemma VARCHAR(200),
    word_sense_id INTEGER REFERENCES word_senses(id),
    mistake_tag VARCHAR(120) NOT NULL,
    prompt TEXT,
    expected_answer VARCHAR(1000),
    user_answer VARCHAR(1000),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_mistake_events_user_id ON mistake_events(user_id);
CREATE INDEX ix_mistake_events_session_id ON mistake_events(session_id);
CREATE INDEX ix_mistake_events_english_lemma ON mistake_events(english_lemma);
CREATE INDEX ix_mistake_events_word_sense_id ON mistake_events(word_sense_id);
CREATE INDEX ix_mistake_events_mistake_tag ON mistake_events(mistake_tag);
CREATE INDEX ix_mistake_events_created_at ON mistake_events(created_at);
