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
            "api", "app", "application", "algorithm", "architecture", "array",
            "authentication", "backend", "browser", "cache", "callback", "code",
            "compile", "component", "computer", "data", "database", "debug",
            "deploy", "device", "digital", "endpoint", "execute", "frontend",
            "function", "implement", "index", "integrate", "interface", "internet",
            "library", "loop", "memory", "merge", "migrate", "module", "network",
            "optimize", "output", "parse", "pipeline", "program", "programming",
            "query", "repository", "request", "response", "runtime", "schema",
            "server", "session", "software", "syntax", "system", "technology",
            "token", "tool", "user", "variable", "version", "web",
        }),
        "business": ("Business", {
            "account", "agreement", "appointment", "arrange", "bank", "budget",
            "business", "cancel", "company", "contract", "convenient", "customer",
            "deadline", "delay", "deliver", "discount", "document", "emergency",
            "estimate", "exchange", "finance", "flexible", "funding", "handle",
            "industry", "invoice", "investor", "manage", "market", "money",
            "negotiate", "office", "organization", "organize", "payment", "price",
            "priority", "professional", "profit", "project", "refund", "reliable",
            "remind", "revenue", "schedule", "startup", "succeed", "sufficient",
            "task", "team", "trade", "urgent", "work", "workplace",
        }),
        "travel": ("Travel", {
            "airport", "beach", "booking", "city", "flight", "hotel", "journey",
            "map", "passport", "river", "road", "ticket", "tour", "train",
            "travel", "trip", "visit",
        }),
        "education": ("Education", {
            "book", "class", "classroom", "college", "course", "curriculum",
            "degree", "diploma", "exam", "exercise", "grade", "graduation",
            "homework", "instructor", "knowledge", "learn", "lecture", "lesson",
            "literacy", "practice", "pupil", "qualification", "quiz", "read",
            "school", "skill", "student", "study", "teacher", "test",
            "textbook", "training", "tutor", "university",
        }),
        "academic": ("Academic", {
            "abstract", "accuracy", "analyze", "approach", "assess", "category",
            "clarify", "classify", "conclude", "confirm", "consistent",
            "construct", "contribute", "critical", "demonstrate", "derive",
            "determine", "distribute", "domain", "emphasize", "empirical",
            "evaluate", "experiment", "framework", "generate", "hypothesis",
            "indicate", "interpret", "investigate", "justify", "methodology",
            "observation", "outcome", "parameter", "phenomenon", "propose",
            "publish", "research", "review", "significant", "synthesize",
            "theory", "validate", "variable",
        }),
        "daily-life": ("Daily Life", {
            "apple", "attend", "buy", "complain", "cook", "day", "eat",
            "family", "food", "friend", "go", "home", "house", "life",
            "morning", "progress", "shop", "street", "time", "variety",
            "volunteer", "water",
        }),
        "nature": ("Nature", {
            "animal", "environment", "forest", "garden", "lake", "mountain",
            "nature", "plant", "rain", "river", "sea", "sky", "tree", "weather",
        }),
        "arts-media": ("Arts & Media", {
            "actor", "author", "biography", "book", "cast", "character",
            "chapter", "cinema", "classic", "comedy", "critic", "dialogue",
            "director", "documentary", "drama", "episode", "fiction", "film",
            "genre", "hero", "heroine", "horror", "literature", "movie",
            "narrative", "narrator", "novel", "plot", "poetry", "protagonist",
            "quote", "reader", "scene", "screenplay", "sequel", "series",
            "setting", "show", "story", "subtitle", "theme", "thriller",
            "villain", "voice", "writer",
        }),
        "law": ("Law", {
            "accusation", "acquit", "appeal", "arbitration", "attorney",
            "breach", "case", "civil", "clause", "compensation", "compliance",
            "constitution", "contract", "conviction", "court", "crime",
            "criminal", "damages", "defendant", "dispute", "enforcement",
            "evidence", "fine", "fraud", "guilty", "hearing", "illegal",
            "injunction", "judge", "judgment", "jurisdiction", "jury",
            "justice", "law", "lawsuit", "legal", "legislation", "liability",
            "litigation", "negligence", "obligation", "offense", "penalty",
            "plaintiff", "prison", "prosecution", "regulation", "rights",
            "statute", "testimony", "trial", "verdict", "violation", "witness",
        }),
        "medicine": ("Medicine", {
            "anatomy", "antibiotic", "blood", "brain", "cancer", "cardiology",
            "cell", "chronic", "clinic", "diagnosis", "disease", "disorder",
            "dose", "drug", "emergency", "epidemic", "examination", "genetic",
            "heart", "hormone", "hospital", "immune", "infection", "injury",
            "medicine", "mental", "nerve", "neurology", "nutrition", "organ",
            "pain", "patient", "pharmacy", "physician", "prescription",
            "prevention", "psychology", "recovery", "rehabilitation", "surgery",
            "symptom", "therapy", "treatment", "vaccination", "virus", "wound",
        }),
        "science": ("Science", {
            "atom", "biology", "chemistry", "climate", "cosmos", "element",
            "energy", "entropy", "evolution", "experiment", "force", "formula",
            "galaxy", "gravity", "laboratory", "mass", "mathematics", "matter",
            "molecule", "nucleus", "orbit", "particle", "physics", "planet",
            "quantum", "radiation", "reaction", "relativity", "space",
            "spectrum", "statistics", "universe", "velocity", "wave",
        }),
        "economics": ("Economics", {
            "capital", "commodity", "competition", "consumption", "currency",
            "debt", "demand", "depreciation", "distribution", "dividend",
            "economic", "economy", "employment", "export", "fiscal", "gdp",
            "growth", "import", "income", "index", "inflation", "investment",
            "macroeconomics", "microeconomics", "monetary", "monopoly",
            "recession", "regulation", "subsidy", "supply", "surplus", "tax",
            "trade", "unemployment", "wage",
        }),
        "general": ("General", {
            "ability", "accept", "achieve", "action", "activity", "actually",
            "advantage", "affect", "agree", "allow", "amount", "apply", "argue",
            "aspect", "assume", "attempt", "attitude", "available", "avoid",
            "aware", "balance", "behavior", "benefit", "beyond", "cause",
            "challenge", "change", "character", "claim", "clear", "compare",
            "complete", "complex", "concept", "concern", "condition", "consider",
            "continue", "control", "create", "culture", "current", "decision",
            "define", "describe", "develop", "difference", "difficult", "discuss",
            "effect", "effort", "element", "enable", "exist", "expect",
            "experience", "factor", "feature", "focus", "follow", "force",
            "form", "goal", "growth", "identify", "impact", "important",
            "improve", "include", "increase", "individual", "influence",
            "information", "interest", "involve", "issue", "language", "lead",
            "level", "likely", "limit", "maintain", "matter", "meaning",
            "measure", "method", "mind", "model", "necessary", "objective",
            "opinion", "opportunity", "order", "overall", "participate",
            "particular", "pattern", "perform", "period", "perspective",
            "plan", "point", "policy", "position", "positive", "possible",
            "present", "prevent", "principle", "process", "produce", "provide",
            "purpose", "quality", "range", "reason", "reduce", "relate",
            "relevant", "require", "resource", "respond", "result", "role",
            "situation", "society", "solution", "source", "specific", "strategy",
            "structure", "suggest", "support", "therefore", "value", "various",
            "view",
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

        return "general", self._display_name("general")

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

        rows = list(self._db.scalars(
            select(DictionaryEntryModel)
            .where(DictionaryEntryModel.topic_cluster_key.in_(interest_keys))
        ))

        best_by_lemma: dict[str, InterestWordItem] = {}
        for entry in rows:
            lemma = entry.english_lemma.strip().lower()
            if not lemma or lemma in saved_lemmas:
                continue
            cluster_key = entry.topic_cluster_key
            if cluster_key not in interests:
                continue
            weight, display_name = interests[cluster_key]
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

        import random
        candidates = list(best_by_lemma.values())
        if not candidates:
            return []
        # general получает 30% от своего веса если есть слова из других категорий
        has_non_general = any(item.primary_signal != "General" for item in candidates)
        weights = [
            item.score * 0.3 if (has_non_general and item.primary_signal == "General") else item.score
            for item in candidates
        ]
        k = min(limit, len(candidates))
        chosen = random.choices(candidates, weights=weights, k=k * 3)
        # Убираем дубли, сохраняя порядок
        seen: set[str] = set()
        result: list[InterestWordItem] = []
        for item in chosen:
            if item.english_lemma not in seen:
                seen.add(item.english_lemma)
                result.append(item)
            if len(result) >= limit:
                break
        # Если не набрали нужное количество — добираем оставшиеся случайно
        if len(result) < k:
            remaining = [i for i in candidates if i.english_lemma not in seen]
            random.shuffle(remaining)
            result.extend(remaining[:k - len(result)])
        return result
