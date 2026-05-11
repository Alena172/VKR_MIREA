from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import Depends

from app.core.db import transaction
from app.modules.ai.facade import ai_facade as ai_service
from app.modules.ai.schemas import ExplainErrorRequest
from app.modules.graph.service.graph import GraphService
from app.modules.review.service.srs import SRSService, WordProgressUpdate
from app.modules.training.repository import AnswerPersistPayload, TrainingRepository
from app.modules.training.schemas import (
    SessionAnswer,
    SessionAnswerFeedbackDTO,
    SessionSubmitResultDTO,
)
from app.modules.training.service.evaluation import (
    answer_similarity_metrics,
    detect_simple_exercise_type,
    evaluate_simple_exercise,
    extract_progress_word,
    is_answer_correct,
    is_semantic_override_candidate,
    normalize_answer,
)


@dataclass
class EvaluatedAnswer:
    exercise_id: int
    exercise_type: str | None
    target_word: str | None
    prompt: str | None
    expected_answer: str | None
    user_answer: str
    is_correct: bool
    explanation_ru: str | None
    progress_word: str | None
    incorrect_feedback: SessionAnswerFeedbackDTO | None
    advice_feedback: SessionAnswerFeedbackDTO | None


_STYLE_ADVICE_MIN_TOKENS = 6
_STYLE_ADVICE_MAX_TOKENS = 24


def _should_run_semantic_check(expected_answer: str | None, user_answer: str | None) -> bool:
    metrics = answer_similarity_metrics(expected_answer, user_answer)
    return (
        metrics["text_similarity"] >= 0.45
        or metrics["token_recall"] >= 0.35
        or metrics["canonical_content_recall"] >= 0.35
    )


def _should_add_style_advice(expected_answer: str | None, user_answer: str | None) -> bool:
    metrics = answer_similarity_metrics(expected_answer, user_answer)
    normalized_expected = normalize_answer(expected_answer)
    normalized_user = normalize_answer(user_answer)
    expected_tokens = normalized_expected.split()
    user_tokens = normalized_user.split()

    if (
        len(expected_tokens) < _STYLE_ADVICE_MIN_TOKENS
        or len(user_tokens) < _STYLE_ADVICE_MIN_TOKENS
        or len(expected_tokens) > _STYLE_ADVICE_MAX_TOKENS
        or len(user_tokens) > _STYLE_ADVICE_MAX_TOKENS
    ):
        return False

    if (
        metrics["canonical_token_recall"] >= 0.92
        and metrics["canonical_content_recall"] >= 0.92
        and metrics["text_similarity"] >= 0.9
    ):
        return False

    high_confidence_semantic_match = (
        metrics["canonical_token_recall"] >= 0.78
        and metrics["canonical_content_recall"] >= 0.82
    )
    noticeable_style_deviation = (
        metrics["text_similarity"] <= 0.9
        or metrics["token_recall"] <= 0.82
        or metrics["content_recall"] <= 0.85
    )
    return high_confidence_semantic_match and noticeable_style_deviation


def _dedupe_answers(answers: list[SessionAnswer]) -> list[SessionAnswer]:
    deduped: dict[int, SessionAnswer] = {}
    for answer in answers:
        deduped[answer.exercise_id] = answer
    return list(deduped.values())


async def _evaluate_answer(answer: SessionAnswer) -> EvaluatedAnswer:
    simple_exercise_type = detect_simple_exercise_type(
        exercise_type=answer.exercise_type,
        prompt=answer.prompt,
        expected_answer=answer.expected_answer,
    )
    if simple_exercise_type in {"word_scramble", "word_definition_match"}:
        evaluated_is_correct, explanation_ru = evaluate_simple_exercise(
            expected_answer=answer.expected_answer,
            user_answer=answer.user_answer,
            exercise_type=simple_exercise_type,
        )
        incorrect_feedback = None
        if not evaluated_is_correct and explanation_ru:
            incorrect_feedback = SessionAnswerFeedbackDTO(
                exercise_id=answer.exercise_id,
                explanation_ru=explanation_ru,
            )
        progress_word = extract_progress_word(
            target_word=answer.target_word,
            prompt=answer.prompt,
            expected_answer=answer.expected_answer,
            vocabulary_words=set(),
        )
        return EvaluatedAnswer(
            exercise_id=answer.exercise_id,
            exercise_type=answer.exercise_type or simple_exercise_type,
            target_word=answer.target_word,
            prompt=answer.prompt,
            expected_answer=answer.expected_answer,
            user_answer=answer.user_answer,
            is_correct=evaluated_is_correct,
            explanation_ru=explanation_ru,
            progress_word=progress_word,
            incorrect_feedback=incorrect_feedback,
            advice_feedback=None,
        )

    evaluated_is_correct = is_answer_correct(answer.expected_answer, answer.user_answer)
    explanation_ru: str | None = None
    advice_feedback: SessionAnswerFeedbackDTO | None = None
    incorrect_feedback: SessionAnswerFeedbackDTO | None = None
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
            or _should_run_semantic_check(answer.expected_answer, answer.user_answer)
        )
    ):
        semantic_ok = await ai_service.is_translation_semantically_correct_async(
            english_prompt=answer.prompt,
            expected_answer=answer.expected_answer,
            user_answer=answer.user_answer,
        )
        if semantic_ok:
            evaluated_is_correct = True
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
        incorrect_feedback = SessionAnswerFeedbackDTO(
            exercise_id=answer.exercise_id,
            explanation_ru=explanation_ru,
        )
    elif (
        evaluated_is_correct
        and answer.prompt
        and answer.expected_answer
        and normalized_expected
        and normalized_expected != normalized_user
        and _should_add_style_advice(answer.expected_answer, answer.user_answer)
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
        advice_feedback = SessionAnswerFeedbackDTO(
            exercise_id=answer.exercise_id,
            explanation_ru=explanation_ru,
        )

    progress_word = extract_progress_word(
        target_word=answer.target_word,
        prompt=answer.prompt,
        expected_answer=answer.expected_answer,
        vocabulary_words=set(),
    )

    return EvaluatedAnswer(
        exercise_id=answer.exercise_id,
        exercise_type=answer.exercise_type,
        target_word=answer.target_word,
        prompt=answer.prompt,
        expected_answer=answer.expected_answer,
        user_answer=answer.user_answer,
        is_correct=evaluated_is_correct,
        explanation_ru=explanation_ru,
        progress_word=progress_word,
        incorrect_feedback=incorrect_feedback,
        advice_feedback=advice_feedback,
    )


async def _evaluate_answers(answers: list[SessionAnswer]) -> list[EvaluatedAnswer]:
    if not answers:
        return []
    semaphore = asyncio.Semaphore(4)

    async def evaluate_with_limit(answer: SessionAnswer) -> EvaluatedAnswer:
        async with semaphore:
            return await _evaluate_answer(answer)

    return await asyncio.gather(*(evaluate_with_limit(answer) for answer in answers))


def _collect_feedback(
    evaluated_answers: list[EvaluatedAnswer],
) -> tuple[list[SessionAnswerFeedbackDTO], list[SessionAnswerFeedbackDTO]]:
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


class SubmissionService:
    def __init__(
        self,
        training_repo: TrainingRepository = Depends(),
        srs_service: SRSService = Depends(),
        graph_service: GraphService = Depends(),
    ) -> None:
        self._training_repo = training_repo
        self._srs_service = srs_service
        self._graph_service = graph_service

    def _update_progress(
        self,
        *,
        user_id: int,
        evaluated_answers: list[EvaluatedAnswer],
    ) -> None:
        progress_updates: list[WordProgressUpdate] = []
        for item in evaluated_answers:
            if item.progress_word:
                progress_updates.append(
                    WordProgressUpdate(word=item.progress_word, is_correct=item.is_correct)
                )
            if item.progress_word and not item.is_correct:
                self._graph_service.register_mistake(
                    user_id=user_id,
                    english_lemma=item.progress_word,
                    prompt=item.prompt,
                    expected_answer=item.expected_answer,
                    user_answer=item.user_answer,
                )

        self._srs_service.update_learning_progress(user_id=user_id, updates=progress_updates)

    def _persist_session(
        self,
        *,
        user_id: int,
        evaluated_answers: list[EvaluatedAnswer],
    ):
        total = len(evaluated_answers)
        correct = sum(1 for item in evaluated_answers if item.is_correct)
        return self._training_repo.create_session_with_answers(
            user_id=user_id,
            total=total,
            correct=correct,
            accuracy=round((correct / total), 4) if total else 0.0,
            answers=[
                AnswerPersistPayload(
                    exercise_id=item.exercise_id,
                    exercise_type=item.exercise_type,
                    target_word=item.target_word,
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

    def list_recent_incorrect_words(
        self,
        *,
        user_id: int,
        limit: int,
        unique: bool = True,
    ) -> list[str]:
        raw = self._training_repo.list_recent_incorrect_answer_data(user_id=user_id, limit=limit)
        words: list[str] = []
        for target_word, prompt in raw:
            word = (target_word or "").strip().lower()
            if not word:
                prompt_text = (prompt or "").strip()
                word = prompt_text.split(":", maxsplit=1)[-1].strip().lower() if prompt_text else ""
            if not word:
                continue
            if unique:
                if word not in words:
                    words.append(word)
            else:
                words.append(word)
        return words

    def get_progress_snapshot(self, *, user_id: int) -> tuple[int, float]:
        return self._training_repo.get_progress_snapshot(user_id=user_id)

    async def submit(
        self,
        *,
        user_id: int,
        answers: list[SessionAnswer],
    ) -> SessionSubmitResultDTO:
        normalized_answers = _dedupe_answers(answers)
        evaluated_answers = await _evaluate_answers(normalized_answers)
        incorrect_feedback, advice_feedback = _collect_feedback(evaluated_answers)
        with transaction(self._training_repo._db):
            self._update_progress(user_id=user_id, evaluated_answers=evaluated_answers)
            session_row = self._persist_session(user_id=user_id, evaluated_answers=evaluated_answers)
        return SessionSubmitResultDTO(
            session=session_row,
            incorrect_feedback=incorrect_feedback,
            advice_feedback=advice_feedback,
        )
