from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.graph.models import (
    SenseErrorEventModel,
    SenseRelationModel,
    TopicClusterModel,
    UserInterestModel,
    VocabularySenseLinkModel,
    WordSenseModel,
)
from app.modules.graph.schemas import InterestItem, InterestWordItem, SenseAnchorItem


@dataclass
class SemanticUpsertResult:
    """Результат создания или переиспользования смысла слова."""

    sense: WordSenseModel
    created_new: bool
    duplicate_of_id: int | None
    cluster: TopicClusterModel | None


@dataclass(frozen=True)
class TopicInference:
    key: str
    display_name: str
    confidence: float


class GraphRepository:
    """Персональный learning graph вокруг интересов и смыслов слов."""

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

    def _semantic_key(self, *, russian_translation: str, source_sentence: str | None, context_definition: str | None, topic_key: str) -> str:
        tokens = sorted(self._tokens(f"{russian_translation} {source_sentence or ''} {context_definition or ''}"))
        if not tokens:
            return topic_key or "generic"
        return "-".join(tokens[:4])[:120]

    def _infer_topic(self, *, english_lemma: str, russian_translation: str, context_definition_ru: str | None, source_sentence: str | None, topic_hint: str | None) -> TopicInference:
        if topic_hint:
            key = self._normalize_interest_key(topic_hint)
            if key:
                return TopicInference(key=key, display_name=self._display_name(key), confidence=1.0)

        tokens = self._tokens(f"{english_lemma} {russian_translation} {context_definition_ru or ''} {source_sentence or ''}")
        topic_scores: Counter[str] = Counter()
        for topic_key, (_, markers) in self._TOPIC_MARKERS.items():
            topic_scores[topic_key] = len(tokens & markers)

        if topic_scores:
            topic_key, score = topic_scores.most_common(1)[0]
            if score > 0:
                return TopicInference(key=topic_key, display_name=self._display_name(topic_key), confidence=min(1.0, 0.45 + 0.15 * score))

        fallback_token = next(iter(sorted(tokens)), "general")
        key = self._normalize_interest_key(fallback_token) or "general"
        return TopicInference(key=key, display_name=self._display_name(key), confidence=0.25)

    def _ensure_cluster(self, *, user_id: int, topic: TopicInference) -> TopicClusterModel:
        row = self._db.scalar(select(TopicClusterModel).where(TopicClusterModel.user_id == user_id, TopicClusterModel.cluster_key == topic.key))
        if row is not None:
            return row
        row = TopicClusterModel(user_id=user_id, cluster_key=topic.key, name=topic.display_name)
        self._db.add(row)
        self._db.flush()
        return row

    def _increase_interest(self, *, user_id: int, topic: TopicInference) -> None:
        row = self._db.scalar(select(UserInterestModel).where(UserInterestModel.user_id == user_id, UserInterestModel.interest_key == topic.key))
        boost = max(0.1, topic.confidence)
        if row is None:
            self._db.add(UserInterestModel(user_id=user_id, interest_key=topic.key, display_name=topic.display_name, weight=round(boost, 4)))
            self._db.flush()
            return
        row.weight = round(min(10.0, row.weight + boost), 4)
        row.display_name = topic.display_name
        self._db.flush()

    def _pair_ids(self, left_id: int, right_id: int) -> tuple[int, int]:
        return (left_id, right_id) if left_id < right_id else (right_id, left_id)

    def _upsert_relation(self, *, user_id: int, left_sense_id: int, right_sense_id: int, relation_type: str, score: float) -> None:
        if left_sense_id == right_sense_id:
            return
        left_id, right_id = self._pair_ids(left_sense_id, right_sense_id)
        existing = self._db.scalar(select(SenseRelationModel).where(
            SenseRelationModel.user_id == user_id,
            SenseRelationModel.left_sense_id == left_id,
            SenseRelationModel.right_sense_id == right_id,
        ))
        if existing is None:
            self._db.add(SenseRelationModel(user_id=user_id, left_sense_id=left_id, right_sense_id=right_id, relation_type=relation_type, score=round(score, 4)))
            self._db.flush()
            return
        if score > existing.score:
            existing.score = round(score, 4)
            existing.relation_type = relation_type
            self._db.flush()

    def _sync_simple_relations(self, *, user_id: int, sense: WordSenseModel) -> None:
        candidates = list(self._db.scalars(select(WordSenseModel).where(
            WordSenseModel.user_id == user_id,
            WordSenseModel.id != sense.id,
            or_(WordSenseModel.english_lemma == sense.english_lemma, WordSenseModel.topic_cluster_id == sense.topic_cluster_id),
        )))
        for candidate in candidates:
            if candidate.english_lemma == sense.english_lemma and candidate.semantic_key != sense.semantic_key:
                self._upsert_relation(user_id=user_id, left_sense_id=sense.id, right_sense_id=candidate.id, relation_type="polysemy_variant", score=0.95)
            elif sense.topic_cluster_id is not None and candidate.topic_cluster_id == sense.topic_cluster_id:
                self._upsert_relation(user_id=user_id, left_sense_id=sense.id, right_sense_id=candidate.id, relation_type="same_interest", score=0.55)

    def list_interests(self, user_id: int) -> list[InterestItem]:
        rows = list(self._db.scalars(select(UserInterestModel).where(UserInterestModel.user_id == user_id).order_by(UserInterestModel.weight.desc(), UserInterestModel.id.asc())))
        return [InterestItem(interest=row.display_name, weight=row.weight) for row in rows]

    def upsert_interests(self, user_id: int, interests: list[InterestItem]) -> list[InterestItem]:
        self._db.query(UserInterestModel).filter(UserInterestModel.user_id == user_id).delete()
        for interest in interests:
            key = self._normalize_interest_key(interest.interest)
            if not key:
                continue
            self._db.add(UserInterestModel(user_id=user_id, interest_key=key, display_name=interest.interest.strip(), weight=interest.weight))
        self._db.flush()
        return self.list_interests(user_id)

    def semantic_upsert(
        self,
        *,
        user_id: int,
        english_lemma: str,
        russian_translation: str,
        context_definition_ru: str | None,
        source_sentence: str | None,
        source_url: str | None,
        topic_hint: str | None = None,
        vocabulary_item_id: int | None = None,
    ) -> SemanticUpsertResult:
        lemma = self._normalize_lemma(english_lemma)
        translation = (russian_translation or "").strip()
        if not lemma or not translation:
            raise ValueError("english_lemma and russian_translation are required")

        topic = self._infer_topic(english_lemma=lemma, russian_translation=translation, context_definition_ru=context_definition_ru, source_sentence=source_sentence, topic_hint=topic_hint)
        cluster = self._ensure_cluster(user_id=user_id, topic=topic)
        semantic_key = self._semantic_key(russian_translation=translation, source_sentence=source_sentence, context_definition=context_definition_ru, topic_key=topic.key)

        existing = self._db.scalar(select(WordSenseModel).where(WordSenseModel.user_id == user_id, WordSenseModel.english_lemma == lemma, WordSenseModel.semantic_key == semantic_key))
        existing_link = None
        if vocabulary_item_id is not None:
            existing_link = self._db.scalar(select(VocabularySenseLinkModel).where(VocabularySenseLinkModel.user_id == user_id, VocabularySenseLinkModel.vocabulary_item_id == vocabulary_item_id))

        if existing is None:
            sense = WordSenseModel(user_id=user_id, english_lemma=lemma, semantic_key=semantic_key, russian_translation=translation, context_definition_ru=context_definition_ru, source_sentence=source_sentence, source_url=source_url, topic_cluster_id=cluster.id)
            self._db.add(sense)
            self._db.flush()
            created_new = True
            duplicate_of_id = None
        else:
            sense = existing
            if sense.topic_cluster_id != cluster.id:
                sense.topic_cluster_id = cluster.id
                self._db.flush()
            created_new = False
            duplicate_of_id = existing.id

        if vocabulary_item_id is not None:
            if existing_link is None:
                self._db.add(VocabularySenseLinkModel(user_id=user_id, vocabulary_item_id=vocabulary_item_id, word_sense_id=sense.id))
                self._db.flush()
            elif existing_link.word_sense_id != sense.id:
                existing_link.word_sense_id = sense.id
                self._db.flush()

        self._increase_interest(user_id=user_id, topic=topic)
        self._sync_simple_relations(user_id=user_id, sense=sense)
        self._db.flush()
        self._db.refresh(sense)

        return SemanticUpsertResult(sense=sense, created_new=created_new, duplicate_of_id=duplicate_of_id, cluster=cluster)

    def add_sense_error_event(
        self,
        *,
        user_id: int,
        english_lemma: str | None,
        prompt: str | None,
        expected_answer: str | None,
        user_answer: str | None,
        session_id: int | None = None,
    ) -> SenseErrorEventModel | None:
        lemma = self._normalize_lemma(english_lemma or "")
        if not lemma:
            return None
        sense = self._db.scalar(select(WordSenseModel).where(WordSenseModel.user_id == user_id, WordSenseModel.english_lemma == lemma).order_by(WordSenseModel.id.desc()))
        row = SenseErrorEventModel(user_id=user_id, session_id=session_id, english_lemma=lemma, word_sense_id=sense.id if sense is not None else None, mistake_tag="learning_session_error", prompt=prompt, expected_answer=expected_answer, user_answer=user_answer)
        self._db.add(row)
        self._db.flush()
        return row

    def delete_vocabulary_links(self, *, user_id: int, vocabulary_item_id: int) -> int:
        rows = list(self._db.scalars(select(VocabularySenseLinkModel).where(VocabularySenseLinkModel.user_id == user_id, VocabularySenseLinkModel.vocabulary_item_id == vocabulary_item_id)))
        for row in rows:
            self._db.delete(row)
        if rows:
            self._db.flush()
        return len(rows)

    def list_interest_words(self, *, user_id: int, limit: int, known_lemmas: set[str] | None = None) -> list[InterestWordItem]:
        interests = {row.interest_key: row.weight for row in self._db.scalars(select(UserInterestModel).where(UserInterestModel.user_id == user_id))}
        if not interests:
            return []

        clusters = {row.id: row for row in self._db.scalars(select(TopicClusterModel).where(TopicClusterModel.user_id == user_id))}
        known_lemmas = known_lemmas or set()
        best_by_lemma: dict[str, InterestWordItem] = {}
        for sense in self._db.scalars(select(WordSenseModel).where(WordSenseModel.user_id == user_id)):
            lemma = sense.english_lemma.strip().lower()
            if not lemma:
                continue
            cluster = clusters.get(sense.topic_cluster_id) if sense.topic_cluster_id else None
            interest_weight = interests.get(cluster.cluster_key, 0.0) if cluster else 0.0
            if interest_weight <= 0:
                continue
            score = interest_weight * (0.35 if lemma in known_lemmas else 1.0)
            reasons = ["interest_profile"] + (["already_saved"] if lemma in known_lemmas else [])
            item = InterestWordItem(english_lemma=lemma, russian_translation=sense.russian_translation, score=round(score, 4), reasons=reasons, profile_signals=["InterestProfile"], primary_signal="InterestProfile")
            current = best_by_lemma.get(lemma)
            if current is None or item.score > current.score:
                best_by_lemma[lemma] = item

        items = sorted(best_by_lemma.values(), key=lambda row: (row.score, row.english_lemma), reverse=True)
        return items[:limit]

    def list_anchors(self, *, user_id: int, english_lemma: str, limit: int) -> list[SenseAnchorItem]:
        lemma = self._normalize_lemma(english_lemma)
        if not lemma:
            return []

        source = self._db.scalar(select(WordSenseModel).where(WordSenseModel.user_id == user_id, WordSenseModel.english_lemma == lemma).order_by(WordSenseModel.id.desc()))
        if source is None:
            return []

        relations = list(self._db.scalars(select(SenseRelationModel).where(
            SenseRelationModel.user_id == user_id,
            or_(SenseRelationModel.left_sense_id == source.id, SenseRelationModel.right_sense_id == source.id),
        )))
        neighbor_ids = {
            relation.right_sense_id if relation.left_sense_id == source.id else relation.left_sense_id
            for relation in relations
        }
        neighbors = {
            row.id: row
            for row in self._db.scalars(select(WordSenseModel).where(WordSenseModel.user_id == user_id, WordSenseModel.id.in_(neighbor_ids)))
        } if neighbor_ids else {}

        anchors: list[SenseAnchorItem] = []
        for relation in relations:
            neighbor_id = relation.right_sense_id if relation.left_sense_id == source.id else relation.left_sense_id
            neighbor = neighbors.get(neighbor_id)
            if neighbor is None:
                continue
            anchors.append(SenseAnchorItem(english_lemma=neighbor.english_lemma, russian_translation=neighbor.russian_translation, relation_type=relation.relation_type, score=round(relation.score, 4)))

        anchors.sort(key=lambda row: (row.relation_type != "polysemy_variant", -row.score, row.english_lemma))
        return anchors[:limit]
