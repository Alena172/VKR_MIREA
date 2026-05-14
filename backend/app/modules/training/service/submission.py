from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends

from app.core.db import transaction
from app.modules.graph.service.graph import GraphService
from app.modules.review.service.srs import SRSService, WordProgressUpdate
from app.modules.training.repository import AnswerPersistPayload, TrainingRepository
from app.modules.training.schemas import (
    SessionAnswer,
    SessionSubmitResultDTO,
)
from app.modules.training.service.evaluation import (
    detect_simple_exercise_type,
    evaluate_simple_exercise,
    is_answer_correct,
)


@dataclass
class EvaluatedAnswer:
    exercise_id: int
    exercise_type: str | None
    target_word: str | None
    vocabulary_id: int | None
    prompt: str | None
    expected_answer: str | None
    user_answer: str
    is_correct: bool


def _dedupe_answers(answers: list[SessionAnswer]) -> list[SessionAnswer]:
    deduped: dict[int, SessionAnswer] = {}
    for answer in answers:
        deduped[answer.exercise_id] = answer
    return list(deduped.values())


def _evaluate_answer(answer: SessionAnswer) -> EvaluatedAnswer:
    simple_exercise_type = detect_simple_exercise_type(
        exercise_type=answer.exercise_type,
        prompt=answer.prompt,
        expected_answer=answer.expected_answer,
    )
    if simple_exercise_type in {"word_scramble", "word_definition_match"}:
        is_correct, _ = evaluate_simple_exercise(
            expected_answer=answer.expected_answer,
            user_answer=answer.user_answer,
            exercise_type=simple_exercise_type,
        )
        return EvaluatedAnswer(
            exercise_id=answer.exercise_id,
            exercise_type=answer.exercise_type or simple_exercise_type,
            target_word=answer.target_word,
            vocabulary_id=answer.vocabulary_id,
            prompt=answer.prompt,
            expected_answer=answer.expected_answer,
            user_answer=answer.user_answer,
            is_correct=is_correct,
        )

    return EvaluatedAnswer(
        exercise_id=answer.exercise_id,
        exercise_type=answer.exercise_type,
        target_word=answer.target_word,
        vocabulary_id=answer.vocabulary_id,
        prompt=answer.prompt,
        expected_answer=answer.expected_answer,
        user_answer=answer.user_answer,
        is_correct=is_answer_correct(answer.expected_answer, answer.user_answer),
    )


def _evaluate_answers(answers: list[SessionAnswer]) -> list[EvaluatedAnswer]:
    return [_evaluate_answer(answer) for answer in answers]


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
            if item.vocabulary_id is not None:
                progress_updates.append(
                    WordProgressUpdate(vocabulary_id=item.vocabulary_id, is_correct=item.is_correct)
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
                    explanation_ru=None,
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

    def submit(
        self,
        *,
        user_id: int,
        answers: list[SessionAnswer],
    ) -> SessionSubmitResultDTO:
        normalized_answers = _dedupe_answers(answers)
        evaluated_answers = _evaluate_answers(normalized_answers)
        with transaction(self._training_repo._db):
            self._update_progress(user_id=user_id, evaluated_answers=evaluated_answers)
            session_row = self._persist_session(user_id=user_id, evaluated_answers=evaluated_answers)
        return SessionSubmitResultDTO(
            session=session_row,
            incorrect_feedback=[],
            advice_feedback=[],
        )
