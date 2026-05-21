from __future__ import annotations

import json
import random
import re

import logging

from app.modules.ai.facade import ai_facade as ai_service
from app.modules.ai.schemas import ExerciseSeed
from app.modules.training.schemas import ExerciseDTO

logger = logging.getLogger(__name__)


def _topic_display_name(topic_cluster_key: str | None) -> str | None:
    if not topic_cluster_key:
        return None
    from app.modules.graph.repository import GraphRepository
    entry = GraphRepository._TOPIC_MARKERS.get(topic_cluster_key)
    if entry:
        return entry[0]
    return topic_cluster_key.replace("-", " ").title()


def _is_valid_sentence_answer(sentence_ru: str | None) -> bool:
    if not sentence_ru:
        return False
    all_words = re.findall(r"[А-Яа-яЁёA-Za-z]+", sentence_ru)
    if len(all_words) < 3:
        return False
    ru_words = [w for w in all_words if re.search(r"[А-Яа-яЁё]", w)]
    return len(ru_words) / len(all_words) >= 0.7


class ExerciseBuilder:
    _FAST_START_EN_TEMPLATES = (
        "The key word is {word}.",
        "Today's word is {word}.",
        "Please remember the word {word}.",
    )
    _FAST_START_RU_TEMPLATES = (
        "Ключевое слово — {translation}.",
        "Слово на сегодня — {translation}.",
        "Пожалуйста, запомни слово {translation}.",
    )

    async def build_items(
        self,
        *,
        seeds: list[ExerciseSeed],
        size: int,
        mode: str,
        cefr_level: str,
        fast_start: bool = False,
    ) -> tuple[list[ExerciseDTO], str]:
        if not seeds:
            return [], "local_heuristic exercise_generation.empty_vocabulary"

        if fast_start and mode == "sentence_translation_full":
            items = [
                self._build_fast_start_sentence_translation_exercise(seeds[idx % len(seeds)])
                for idx in range(size)
            ]
            level_note = f" CEFR={cefr_level}." if cefr_level else ""
            return items, f"local_fast_start_template{level_note}"

        effective_size = min(size, len(seeds))
        scheduled_seeds = seeds[:effective_size]

        if mode == "word_scramble":
            items = []
            for seed in scheduled_seeds:
                try:
                    items.append(self._build_word_scramble_exercise(seed))
                except Exception:
                    pass
        elif mode == "word_definition_match":
            items = []
            for idx, seed in enumerate(scheduled_seeds):
                try:
                    start = idx % len(seeds)
                    rotated_pool = seeds[start:] + seeds[:start]
                    items.append(self._build_word_definition_match_exercise(seed, rotated_pool))
                except Exception:
                    pass
        else:
            items = await self._build_sentence_translation_batch(
                seeds=scheduled_seeds,
                cefr_level=cefr_level,
            )
        level_note = f" CEFR={cefr_level}." if cefr_level else ""
        provider_note = (
            f"remote_sentence_pipeline{level_note}"
            if mode == "sentence_translation_full"
            else f"local_heuristic exercise_generation.{level_note}"
        )
        return items, provider_note

    def _is_word_scramble_suitable(self, word: str) -> bool:
        clean_word = re.sub(r"[^a-z]", "", word.strip().lower())
        if len(clean_word) < 3 or len(clean_word) > 15:
            return False
        return clean_word.isalpha()

    def _build_word_scramble_letters(self, answer: str) -> list[str]:
        clean = re.sub(r"[^a-z]", "", answer.strip().lower())
        if not self._is_word_scramble_suitable(clean):
            return []

        letters = list(clean)
        scrambled = letters.copy()
        seeded_random = random.Random(clean)

        for _ in range(10):
            seeded_random.shuffle(scrambled)
            if scrambled != letters:
                break

        if scrambled == letters and len(scrambled) >= 2:
            scrambled[0], scrambled[-1] = scrambled[-1], scrambled[0]

        return [char.upper() for char in scrambled]

    def _sanitize_definition_for_match(self, word: str, definition: str) -> str:
        cleaned = re.sub(r"\s+", " ", (definition or "").strip())
        if not cleaned:
            return ""

        lemma = word.strip().lower()
        pattern = re.compile(rf"\b{re.escape(lemma)}s?\b", flags=re.IGNORECASE)
        cleaned = pattern.sub("it", cleaned)
        cleaned = re.sub(r"^(an?|the)\s+it\s+(is|are)\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^it\s+(is|are)\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")

        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        if cleaned and cleaned[-1] not in ".!?":
            cleaned = f"{cleaned}."
        return cleaned

    async def _build_sentence_translation_batch(
        self,
        seeds: list[ExerciseSeed],
        cefr_level: str,
    ) -> list[ExerciseDTO]:
        """Генерирует упражнения батчами по 5: один LLM-запрос на 5 слов.
        Для слов, где батч вернул None, делает одиночный повторный запрос."""
        BATCH_SIZE = 5
        items: list[ExerciseDTO] = []
        fallback_seeds: list[ExerciseSeed] = []

        for batch_start in range(0, len(seeds), BATCH_SIZE):
            batch = seeds[batch_start: batch_start + BATCH_SIZE]
            pairs = await ai_service.generate_sentence_batch_async(batch, cefr_level=cefr_level)
            ok = sum(1 for p in pairs if p is not None)
            logger.info("batch generation: %d/%d succeeded for batch starting at %d", ok, len(batch), batch_start)
            for seed, pair in zip(batch, pairs):
                if pair is not None:
                    sentence_en, sentence_ru = pair
                    items.append(ExerciseDTO(
                        prompt=f"Translate sentence into Russian: {sentence_en}",
                        answer=sentence_ru,
                        exercise_type="sentence_translation_full",
                        target_word=seed.english_lemma.strip().lower(),
                        options=[],
                        topic_cluster_key=seed.topic_cluster_key,
                        topic_display_name=_topic_display_name(seed.topic_cluster_key),
                    ))
                else:
                    fallback_seeds.append(seed)

        # Одиночный фолбэк для слов, где батч не сработал
        import asyncio
        semaphore = asyncio.Semaphore(4)

        async def _single(seed: ExerciseSeed) -> ExerciseDTO | None:
            async with semaphore:
                try:
                    return await self._build_sentence_translation_exercise(seed, cefr_level=cefr_level)
                except Exception:
                    return None

        if fallback_seeds:
            fallback_results = await asyncio.gather(*(_single(s) for s in fallback_seeds))
            items.extend(r for r in fallback_results if r is not None)

        return items

    def _build_fast_start_sentence_translation_exercise(self, seed: ExerciseSeed) -> ExerciseDTO:
        normalized_word = seed.english_lemma.strip().lower()
        translation = seed.russian_translation.strip()
        template_index = sum(ord(char) for char in normalized_word) % len(self._FAST_START_EN_TEMPLATES)
        sentence_en = self._FAST_START_EN_TEMPLATES[template_index].format(word=normalized_word)
        sentence_ru = self._FAST_START_RU_TEMPLATES[template_index].format(translation=translation)
        return ExerciseDTO(
            prompt=f"Translate sentence into Russian: {sentence_en}",
            answer=sentence_ru,
            exercise_type="sentence_translation_full",
            target_word=normalized_word,
            options=[],
            topic_cluster_key=seed.topic_cluster_key,
            topic_display_name=_topic_display_name(seed.topic_cluster_key),
        )

    async def _build_sentence_translation_exercise(
        self,
        seed: ExerciseSeed,
        *,
        cefr_level: str | None = None,
    ) -> ExerciseDTO:
        level = (cefr_level or "A2").upper()
        pair = await ai_service.generate_sentence_pair_async(seed=seed, cefr_level=level)
        if pair is None:
            raise ValueError(f"Failed to generate sentence pair for '{seed.english_lemma}'")
        sentence_en, sentence_ru = pair
        if not _is_valid_sentence_answer(sentence_ru):
            raise ValueError(f"Invalid answer generated for '{seed.english_lemma}': {sentence_ru!r}")
        return ExerciseDTO(
            prompt=f"Translate sentence into Russian: {sentence_en}",
            answer=sentence_ru,
            exercise_type="sentence_translation_full",
            target_word=seed.english_lemma.strip().lower(),
            options=[],
            topic_cluster_key=seed.topic_cluster_key,
            topic_display_name=_topic_display_name(seed.topic_cluster_key),
        )

    def _build_word_definition_match_exercise(
        self,
        seed: ExerciseSeed,
        pool: list[ExerciseSeed],
    ) -> ExerciseDTO:
        selected_words: list[ExerciseSeed] = []
        seen: set[str] = set()
        for candidate in [seed] + pool:
            key = candidate.english_lemma.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            selected_words.append(candidate)
            if len(selected_words) == 4:
                break

        if len(selected_words) < 4:
            raise ValueError("Need at least 4 unique words to build a local definition match exercise.")

        pairs = []
        for item in selected_words:
            definition = (item.context_definition_ru or "").strip()
            if not definition:
                raise ValueError("Definition match exercise requires stored definitions in vocabulary.")
            sanitized_definition = self._sanitize_definition_for_match(item.english_lemma, definition)
            if not sanitized_definition:
                raise ValueError("Definition match exercise requires non-empty stored definitions in vocabulary.")
            pairs.append({"word": item.english_lemma.strip().lower(), "definition": sanitized_definition})

        definitions = [pair["definition"] for pair in pairs]
        random.Random("|".join(pair["word"] for pair in pairs)).shuffle(definitions)
        prompt_words = " - ".join([f"{idx}. {pair['word']}" for idx, pair in enumerate(pairs, start=1)])
        return ExerciseDTO(
            prompt=f"Match each word with its definition: {prompt_words}",
            answer=json.dumps(pairs, ensure_ascii=False),
            exercise_type="word_definition_match",
            target_word=None,
            options=definitions,
            topic_cluster_key=seed.topic_cluster_key,
            topic_display_name=_topic_display_name(seed.topic_cluster_key),
        )

    def _build_word_scramble_exercise(self, seed: ExerciseSeed) -> ExerciseDTO:
        normalized_answer = re.sub(r"[^a-z]", "", seed.english_lemma.strip().lower())
        letters = self._build_word_scramble_letters(normalized_answer)
        if not letters:
            raise ValueError("Word scramble requires an alphabetic word between 3 and 15 characters.")
        return ExerciseDTO(
            prompt=f"Assemble the word from letters. Translation hint: {seed.russian_translation}",
            answer=normalized_answer,
            exercise_type="word_scramble",
            target_word=normalized_answer,
            options=letters,
            topic_cluster_key=seed.topic_cluster_key,
            topic_display_name=_topic_display_name(seed.topic_cluster_key),
        )


exercise_builder = ExerciseBuilder()
