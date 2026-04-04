from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import re

from app.core.application import application_transaction
from sqlalchemy.orm import Session

from app.modules.ai_services.contracts import ExplainErrorRequest
from app.modules.ai_services.service import ai_service
from app.modules.context_memory.public_api import WordProgressUpdate, context_memory_public_api
from app.modules.learning_graph.public_api import learning_graph_public_api
from app.modules.learning_session.evaluation import (
    answer_similarity_metrics,
    is_answer_correct,
    is_semantic_override_candidate,
    normalize_answer,
)
from app.modules.learning_session.repository import AnswerPersistPayload, learning_session_repository
from app.modules.learning_session.schemas import (
    SessionAnswer,
    SessionAnswerFeedback,
    SessionSubmitResponse,
)

_WORD_RE = re.compile(r"^[a-z][a-z'-]{0,48}$")
_WHITESPACE_RE = re.compile(r"\s+")
_SCRAMBLE_PROMPT_PREFIX = "assemble the word from letters"
_DEFINITION_MATCH_PROMPT_PREFIX = "match each word with its definition"


def _normalize_text_fragment(value: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip()).casefold()


def _detect_simple_exercise_type(
    *,
    prompt: str | None,
    expected_answer: str | None,
) -> str | None:
    normalized_prompt = _normalize_text_fragment(prompt)
    if normalized_prompt.startswith(_SCRAMBLE_PROMPT_PREFIX):
        return "word_scramble"
    if normalized_prompt.startswith(_DEFINITION_MATCH_PROMPT_PREFIX):
        return "word_definition_match"

    raw_expected = (expected_answer or "").strip()
    if raw_expected.startswith("[") and raw_expected.endswith("]"):
        try:
            parsed = json.loads(raw_expected)
        except Exception:
            return None
        if (
            isinstance(parsed, list)
            and parsed
            and all(
                isinstance(item, dict)
                and isinstance(item.get("word"), str)
                and isinstance(item.get("definition"), str)
                for item in parsed
            )
        ):
            return "word_definition_match"
    return None


def _normalize_scramble_answer(value: str | None) -> str:
    return re.sub(r"[^a-z]", "", (value or "").strip().lower())


def _parse_definition_match_pairs(raw_value: str | None) -> dict[str, str] | None:
    try:
        parsed = json.loads((raw_value or "").strip())
    except Exception:
        return None

    if not isinstance(parsed, list):
        return None

    result: dict[str, str] = {}
    for item in parsed:
        if not isinstance(item, dict):
            return None
        word = _normalize_word_candidate(item.get("word"))
        definition = _normalize_text_fragment(item.get("definition"))
        if not word or not definition:
            return None
        result[word] = definition
    return result or None


def _evaluate_simple_exercise(
    *,
    prompt: str | None,
    expected_answer: str | None,
    user_answer: str | None,
    exercise_type: str,
) -> tuple[bool, str | None]:
    if exercise_type == "word_scramble":
        is_correct = _normalize_scramble_answer(expected_answer) == _normalize_scramble_answer(user_answer)
        explanation_ru = None if is_correct else "Слово собрано неверно."
        return is_correct, explanation_ru

    if exercise_type == "word_definition_match":
        expected_pairs = _parse_definition_match_pairs(expected_answer)
        user_pairs = _parse_definition_match_pairs(user_answer)
        is_correct = bool(expected_pairs and user_pairs and expected_pairs == user_pairs)
        explanation_ru = None if is_correct else "Есть неверные сопоставления между словами и определениями."
        return is_correct, explanation_ru

    return False, None


def _normalize_word_candidate(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().lower().strip(" \t\n\r\"'`.,!?;:()[]{}")
    if not candidate or not _WORD_RE.fullmatch(candidate):
        return None
    return candidate


def _extract_progress_word(
    *,
    prompt: str | None,
    expected_answer: str | None,
    vocabulary_words: set[str],
) -> str | None:
    normalized_answer = _normalize_word_candidate(expected_answer)
    if normalized_answer and (not vocabulary_words or normalized_answer in vocabulary_words):
        return normalized_answer

    if not prompt:
        return None

    after_colon = prompt.split(":", maxsplit=1)[-1]
    normalized_prompt_word = _normalize_word_candidate(after_colon)
    if normalized_prompt_word and (not vocabulary_words or normalized_prompt_word in vocabulary_words):
        return normalized_prompt_word

    return None


@dataclass
class EvaluatedAnswer:
    exercise_id: int
    prompt: str | None
    expected_answer: str | None
    user_answer: str
    is_correct: bool
    explanation_ru: str | None
    progress_word: str | None
    add_to_difficult_words: bool
    incorrect_feedback: SessionAnswerFeedback | None
    advice_feedback: SessionAnswerFeedback | None


class LearningSessionSubmissionService:
    def _should_run_semantic_check(self, expected_answer: str | None, user_answer: str | None) -> bool:
        metrics = answer_similarity_metrics(expected_answer, user_answer)
        return (
            metrics["text_similarity"] >= 0.45
            or metrics["token_recall"] >= 0.35
            or metrics["canonical_content_recall"] >= 0.35
        )

    def _should_add_style_advice(self, expected_answer: str | None, user_answer: str | None) -> bool:
        metrics = answer_similarity_metrics(expected_answer, user_answer)
        return not (
            metrics["canonical_token_recall"] >= 0.92
            and metrics["canonical_content_recall"] >= 0.92
        )

    def _dedupe_answers(self, answers: list[SessionAnswer]) -> list[SessionAnswer]:
        deduped: dict[int, SessionAnswer] = {}
        for answer in answers:
            deduped[answer.exercise_id] = answer
        return list(deduped.values())

    async def evaluate_answers(self, answers: list[SessionAnswer]) -> list[EvaluatedAnswer]:
        if not answers:
            return []

        semaphore = asyncio.Semaphore(4)

        async def evaluate_with_limit(answer: SessionAnswer) -> EvaluatedAnswer:
            async with semaphore:
                return await self._evaluate_answer(answer)

        return await asyncio.gather(*(evaluate_with_limit(answer) for answer in answers))

    async def _evaluate_answer(self, answer: SessionAnswer) -> EvaluatedAnswer:
        simple_exercise_type = _detect_simple_exercise_type(
            prompt=answer.prompt,
            expected_answer=answer.expected_answer,
        )
        if simple_exercise_type in {"word_scramble", "word_definition_match"}:
            evaluated_is_correct, explanation_ru = _evaluate_simple_exercise(
                prompt=answer.prompt,
                expected_answer=answer.expected_answer,
                user_answer=answer.user_answer,
                exercise_type=simple_exercise_type,
            )
            incorrect_feedback = None
            if not evaluated_is_correct and explanation_ru:
                incorrect_feedback = SessionAnswerFeedback(
                    exercise_id=answer.exercise_id,
                    explanation_ru=explanation_ru,
                )

            progress_word = _extract_progress_word(
                prompt=answer.prompt,
                expected_answer=answer.expected_answer,
                vocabulary_words=set(),
            )

            return EvaluatedAnswer(
                exercise_id=answer.exercise_id,
                prompt=answer.prompt,
                expected_answer=answer.expected_answer,
                user_answer=answer.user_answer,
                is_correct=evaluated_is_correct,
                explanation_ru=explanation_ru,
                progress_word=progress_word,
                add_to_difficult_words=bool(progress_word and not evaluated_is_correct),
                incorrect_feedback=incorrect_feedback,
                advice_feedback=None,
            )

        evaluated_is_correct = is_answer_correct(answer.expected_answer, answer.user_answer)
        explanation_ru: str | None = None
        advice_feedback: SessionAnswerFeedback | None = None
        incorrect_feedback: SessionAnswerFeedback | None = None
        normalized_expected = normalize_answer(answer.expected_answer)
        normalized_user = normalize_answer(answer.user_answer)
        advice_added = False

        if (
            not evaluated_is_correct
            and answer.prompt
            and answer.expected_answer
            and len(normalized_expected.split()) >= 5
            and (
                is_semantic_override_candidate(answer.expected_answer, answer.user_answer)
                or self._should_run_semantic_check(answer.expected_answer, answer.user_answer)
            )
        ):
            semantic_ok = await ai_service.is_translation_semantically_correct_async(
                english_prompt=answer.prompt,
                expected_answer=answer.expected_answer,
                user_answer=answer.user_answer,
            )
            if semantic_ok:
                evaluated_is_correct = True
                ai_hint = await ai_service.suggest_improvement_async(
                    ExplainErrorRequest(
                        english_prompt=answer.prompt,
                        user_answer=answer.user_answer,
                        expected_answer=answer.expected_answer,
                    )
                )
                explanation_ru = ai_hint.explanation_ru
                advice_feedback = SessionAnswerFeedback(
                    exercise_id=answer.exercise_id,
                    explanation_ru=explanation_ru,
                )
                advice_added = True

        if not evaluated_is_correct and answer.prompt and answer.expected_answer:
            ai_explanation = await ai_service.explain_error_async(
                ExplainErrorRequest(
                    english_prompt=answer.prompt,
                    user_answer=answer.user_answer,
                    expected_answer=answer.expected_answer,
                )
            )
            explanation_ru = ai_explanation.explanation_ru
            incorrect_feedback = SessionAnswerFeedback(
                exercise_id=answer.exercise_id,
                explanation_ru=explanation_ru,
            )
        elif (
            evaluated_is_correct
            and answer.prompt
            and answer.expected_answer
            and normalized_expected
            and normalized_expected != normalized_user
            and self._should_add_style_advice(answer.expected_answer, answer.user_answer)
            and not advice_added
        ):
            ai_hint = await ai_service.suggest_improvement_async(
                ExplainErrorRequest(
                    english_prompt=answer.prompt,
                    user_answer=answer.user_answer,
                    expected_answer=answer.expected_answer,
                )
            )
            explanation_ru = ai_hint.explanation_ru
            advice_feedback = SessionAnswerFeedback(
                exercise_id=answer.exercise_id,
                explanation_ru=explanation_ru,
            )

        progress_word = _extract_progress_word(
            prompt=answer.prompt,
            expected_answer=answer.expected_answer,
            vocabulary_words=set(),
        )

        return EvaluatedAnswer(
            exercise_id=answer.exercise_id,
            prompt=answer.prompt,
            expected_answer=answer.expected_answer,
            user_answer=answer.user_answer,
            is_correct=evaluated_is_correct,
            explanation_ru=explanation_ru,
            progress_word=progress_word,
            add_to_difficult_words=bool(progress_word and not evaluated_is_correct),
            incorrect_feedback=incorrect_feedback,
            advice_feedback=advice_feedback,
        )

    def collect_feedback(
        self,
        evaluated_answers: list[EvaluatedAnswer],
    ) -> tuple[list[SessionAnswerFeedback], list[SessionAnswerFeedback]]:
        incorrect_feedback = [
            item.incorrect_feedback
            for item in evaluated_answers
            if item.incorrect_feedback is not None
        ]
        advice_feedback = [
            item.advice_feedback
            for item in evaluated_answers
            if item.advice_feedback is not None
        ]
        return incorrect_feedback, advice_feedback

    def update_progress(
        self,
        *,
        db: Session,
        user_id: int,
        user_cefr_level: str | None,
        evaluated_answers: list[EvaluatedAnswer],
    ) -> list[str]:
        progress_updates: list[WordProgressUpdate] = []
        for item in evaluated_answers:
            if item.progress_word:
                progress_updates.append(
                    WordProgressUpdate(
                        word=item.progress_word,
                        is_correct=item.is_correct,
                        mark_difficult=item.add_to_difficult_words,
                    )
                )

            if item.add_to_difficult_words and item.progress_word:
                learning_graph_public_api.register_mistake(
                    db=db,
                    user_id=user_id,
                    english_lemma=item.progress_word,
                    prompt=item.prompt,
                    expected_answer=item.expected_answer,
                    user_answer=item.user_answer,
                )

        result = context_memory_public_api.update_learning_progress(
            db=db,
            user_id=user_id,
            user_cefr_level=user_cefr_level,
            updates=progress_updates,
        )
        return result.difficult_words_added

    def persist_session(
        self,
        *,
        db: Session,
        user_id: int,
        evaluated_answers: list[EvaluatedAnswer],
    ):
        total = len(evaluated_answers)
        correct = sum(1 for item in evaluated_answers if item.is_correct)
        return learning_session_repository.create_with_answers(
            db,
            user_id=user_id,
            total=total,
            correct=correct,
            accuracy=round((correct / total), 4) if total else 0.0,
            answers=[
                AnswerPersistPayload(
                    exercise_id=item.exercise_id,
                    prompt=item.prompt,
                    expected_answer=item.expected_answer,
                    user_answer=item.user_answer,
                    is_correct=item.is_correct,
                    explanation_ru=item.explanation_ru,
                )
                for item in evaluated_answers
            ],
            auto_commit=False,
        )

    async def submit(
        self,
        *,
        db: Session,
        user_id: int,
        user_cefr_level: str | None,
        answers: list[SessionAnswer],
    ) -> SessionSubmitResponse:
        normalized_answers = self._dedupe_answers(answers)
        evaluated_answers = await self.evaluate_answers(normalized_answers)
        incorrect_feedback, advice_feedback = self.collect_feedback(evaluated_answers)
        with application_transaction.boundary(db=db):
            self.update_progress(
                db=db,
                user_id=user_id,
                user_cefr_level=user_cefr_level,
                evaluated_answers=evaluated_answers,
            )
            session_row = self.persist_session(
                db=db,
                user_id=user_id,
                evaluated_answers=evaluated_answers,
            )
        db.refresh(session_row)
        return SessionSubmitResponse(
            session=session_row,
            incorrect_feedback=incorrect_feedback,
            advice_feedback=advice_feedback,
        )


learning_session_submission_service = LearningSessionSubmissionService()
