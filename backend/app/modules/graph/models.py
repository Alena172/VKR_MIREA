from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserInterestModel(Base):
    """Интерес пользователя, выведенный из словаря и контекстов."""

    __tablename__ = "user_interests"
    __table_args__ = (UniqueConstraint("user_id", "interest_key", name="uq_user_interest_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    interest_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class TopicClusterModel(Base):
    """Тематический кластер, к которому могут относиться смыслы слов."""

    __tablename__ = "topic_clusters"
    __table_args__ = (UniqueConstraint("user_id", "cluster_key", name="uq_topic_cluster_user_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    cluster_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class WordSenseModel(Base):
    """Конкретный смысл леммы в контексте пользователя."""

    __tablename__ = "word_senses"
    __table_args__ = (UniqueConstraint("user_id", "english_lemma", "semantic_key", name="uq_word_sense_user_lemma_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    english_lemma: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    semantic_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    russian_translation: Mapped[str] = mapped_column(String(200), nullable=False)
    context_definition_ru: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    topic_cluster_id: Mapped[int | None] = mapped_column(ForeignKey("topic_clusters.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class VocabularySenseLinkModel(Base):
    """Связь словарной записи с выбранным смыслом слова."""

    __tablename__ = "vocabulary_sense_links"
    __table_args__ = (UniqueConstraint("user_id", "vocabulary_item_id", name="uq_vocab_sense_link_user_vocab"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    vocabulary_item_id: Mapped[int] = mapped_column(ForeignKey("user_vocabulary.id", ondelete="CASCADE"), nullable=False, index=True)
    word_sense_id: Mapped[int] = mapped_column(ForeignKey("word_senses.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class SenseRelationModel(Base):
    """Смысловая связь между двумя `WordSense` пользователя."""

    __tablename__ = "sense_relations"
    __table_args__ = (UniqueConstraint("user_id", "left_sense_id", "right_sense_id", name="uq_sense_relation_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    left_sense_id: Mapped[int] = mapped_column(ForeignKey("word_senses.id", ondelete="CASCADE"), nullable=False, index=True)
    right_sense_id: Mapped[int] = mapped_column(ForeignKey("word_senses.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, default="semantic_overlap")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class SenseErrorEventModel(Base):
    """Событие ошибки, привязанное к слову или конкретному смыслу."""

    __tablename__ = "sense_error_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("learning_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    english_lemma: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    word_sense_id: Mapped[int | None] = mapped_column(ForeignKey("word_senses.id", ondelete="SET NULL"), nullable=True, index=True)
    mistake_tag: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_answer: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    user_answer: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
