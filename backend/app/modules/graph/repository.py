from __future__ import annotations

import re
from collections import Counter

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.graph.models import (
    TopicClusterModel,
    UserInterestModel,
)
from app.modules.graph.schemas import InterestItem, InterestWordItem


class GraphRepository:
    """Семантический граф: интересы пользователей и тематические кластеры."""

    _WORD_RE = re.compile(r"[^a-z]+")
    _TAG_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z-]{1,32}")
    _STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "that", "this", "these", "those",
        "with", "from", "into", "onto", "over", "under", "after", "before",
        "during", "while", "through", "about", "around", "against", "between",
        "without", "within", "who", "which", "what", "when", "where", "there",
        "their", "them", "they", "then", "than", "have", "has", "had", "been",
        "being", "was", "were", "are", "is", "am", "do", "does", "did", "can",
        "could", "would", "should", "will", "may", "might", "must", "to", "for",
        "of", "in", "on", "at", "by", "as", "it", "its", "he", "she", "him",
        "her", "you", "your", "we", "our", "not", "very", "more", "most", "less",
        "person", "people", "thing", "something", "someone", "used", "refers",
        "word", "meaning", "means",
    }
    _TOPIC_MARKERS: dict[str, tuple[str, set[str]]] = {
        "technology": ("Technology", {
            "api", "app", "application", "code", "computer", "data", "database",
            "deploy", "device", "digital", "frontend", "backend", "internet",
            "network", "program", "programming", "server", "software", "system",
            "technology", "tool", "user", "web",
        }),
        "business": ("Business", {
            "account", "bank", "budget", "business", "company", "contract",
            "customer", "finance", "funding", "investor", "market", "money",
            "office", "payment", "price", "profit", "project", "revenue",
            "startup", "team", "work",
        }),
        "travel": ("Travel", {
            "airport", "beach", "booking", "city", "flight", "hotel", "journey",
            "map", "passport", "river", "road", "ticket", "tour", "train",
            "travel", "trip", "visit",
        }),
        "education": ("Education", {
            "book", "class", "course", "exam", "exercise", "homework", "learn",
            "lesson", "practice", "read", "school", "skill", "student", "study",
            "teacher", "training", "university",
        }),
        "daily-life": ("Daily Life", {
            "apple", "buy", "cook", "day", "eat", "family", "food", "friend",
            "go", "home", "house", "life", "morning", "shop", "street", "time",
            "water",
        }),
        "nature": ("Nature", {
            "animal", "forest", "garden", "lake", "mountain", "nature", "plant",
            "rain", "river", "sea", "sky", "tree", "weather",
        }),
    }

    def __init__(self, db: Session = Depends(get_db)) -> None:
        self._db = db

    def _normalize_lemma(self, value: str) -> str:
        return self._WORD_RE.sub("", (value or "").strip().lower())

    def _normalize_interest_key(self, value: str) -> str:
        tokens = [token.lower() for token in self._TAG_WORD_RE.findall(value or "")]
        return "-".join(tokens[:3])[:64] if tokens else ""

    def _display_name(self, key: str) -> str:
        for marker_key, (display_name, _) in self._TOPIC_MARKERS.items():
            if marker_key == key:
                return display_name
        return key.replace("-", " ").title()

    def _tokens(self, value: str | None) -> set[str]:
        tokens = {
            token.lower()
            for token in self._TAG_WORD_RE.findall(value or "")
            if len(token) >= 3 and token.lower() not in self._STOPWORDS
        }
        for token in list(tokens):
            if token.endswith("s") and len(token) > 4:
                tokens.add(token[:-1])
        return tokens

    def infer_topic(
        self,
        *,
        english_lemma: str,
        russian_translation: str,
        context_definition_ru: str | None,
        source_sentence: str | None,
        topic_hint: str | None = None,
    ) -> tuple[str, str]:
        """Возвращает (cluster_key, display_name) для слова."""
        if topic_hint:
            key = self._normalize_interest_key(topic_hint)
            if key:
                return key, self._display_name(key)

        tokens = self._tokens(
            f"{english_lemma} {russian_translation} {context_definition_ru or ''} {source_sentence or ''}"
        )
        topic_scores: Counter[str] = Counter()
        for topic_key, (_, markers) in self._TOPIC_MARKERS.items():
            topic_scores[topic_key] = len(tokens & markers)

        if topic_scores:
            topic_key, score = topic_scores.most_common(1)[0]
            if score > 0:
                return topic_key, self._display_name(topic_key)

        fallback_token = next(iter(sorted(tokens)), "general")
        key = self._normalize_interest_key(fallback_token) or "general"
        return key, self._display_name(key)

    def ensure_cluster(self, *, cluster_key: str, display_name: str) -> TopicClusterModel:
        """Возвращает существующий или создаёт новый глобальный кластер."""
        row = self._db.scalar(
            select(TopicClusterModel).where(TopicClusterModel.cluster_key == cluster_key)
        )
        if row is not None:
            return row
        row = TopicClusterModel(cluster_key=cluster_key, name=display_name)
        self._db.add(row)
        self._db.flush()
        return row

    def increase_interest(self, *, user_id: int, cluster_key: str, display_name: str, confidence: float) -> None:
        row = self._db.scalar(
            select(UserInterestModel).where(
                UserInterestModel.user_id == user_id,
                UserInterestModel.interest_key == cluster_key,
            )
        )
        boost = max(0.1, confidence)
        if row is None:
            self._db.add(UserInterestModel(
                user_id=user_id,
                interest_key=cluster_key,
                display_name=display_name,
                weight=round(boost, 4),
            ))
            self._db.flush()
            return
        row.weight = round(min(10.0, row.weight + boost), 4)
        row.display_name = display_name
        self._db.flush()

    def list_interests(self, user_id: int) -> list[InterestItem]:
        rows = list(self._db.scalars(
            select(UserInterestModel)
            .where(UserInterestModel.user_id == user_id)
            .order_by(UserInterestModel.weight.desc(), UserInterestModel.id.asc())
        ))
        return [InterestItem(interest=row.display_name, weight=row.weight) for row in rows]

    def upsert_interests(self, user_id: int, interests: list[InterestItem]) -> list[InterestItem]:
        self._db.query(UserInterestModel).filter(UserInterestModel.user_id == user_id).delete()
        for interest in interests:
            key = self._normalize_interest_key(interest.interest)
            if not key:
                continue
            self._db.add(UserInterestModel(
                user_id=user_id,
                interest_key=key,
                display_name=interest.interest.strip(),
                weight=interest.weight,
            ))
        self._db.flush()
        return self.list_interests(user_id)

    def list_interest_words(
        self,
        *,
        user_id: int,
        limit: int,
        saved_lemmas: set[str] | None = None,
    ) -> list[InterestWordItem]:
        from app.modules.vocabulary.models import DictionaryEntryModel

        interests = {
            row.interest_key: (row.weight, row.display_name)
            for row in self._db.scalars(
                select(UserInterestModel)
                .where(UserInterestModel.user_id == user_id)
                .order_by(UserInterestModel.weight.desc())
            )
        }
        if not interests:
            return []

        interest_keys = list(interests)
        saved_lemmas = saved_lemmas or set()

        rows = list(self._db.execute(
            select(DictionaryEntryModel, TopicClusterModel)
            .join(TopicClusterModel, DictionaryEntryModel.topic_cluster_id == TopicClusterModel.id)
            .where(TopicClusterModel.cluster_key.in_(interest_keys))
        ))

        best_by_lemma: dict[str, InterestWordItem] = {}
        for entry, cluster in rows:
            lemma = entry.english_lemma.strip().lower()
            if not lemma or lemma in saved_lemmas:
                continue
            weight, display_name = interests[cluster.cluster_key]
            item = InterestWordItem(
                english_lemma=lemma,
                russian_translation=entry.russian_translation,
                score=round(weight, 4),
                reasons=["interest_profile"],
                profile_signals=[display_name],
                primary_signal=display_name,
            )
            current = best_by_lemma.get(lemma)
            if current is None or item.score > current.score:
                best_by_lemma[lemma] = item

        items = sorted(best_by_lemma.values(), key=lambda x: (-x.score, x.english_lemma))
        return items[:limit]
