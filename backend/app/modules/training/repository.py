from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.training.models import AnswerModel, LearningSessionModel


@dataclass
class AnswerPersistPayload:
    """Данные ответа, подготовленные к сохранению в БД."""

    exercise_id: int
    exercise_type: str | None
    target_word: str | None
    prompt: str | None
    expected_answer: str | None
    user_answer: str
    is_correct: bool


def _apply_session_filters(
    query: Select,
    *,
    user_id: int | None,
    min_accuracy: float | None = None,
    max_accuracy: float | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> Select:
    if user_id is not None:
        query = query.where(LearningSessionModel.user_id == user_id)
    if min_accuracy is not None:
        query = query.where(LearningSessionModel.accuracy >= min_accuracy)
    if max_accuracy is not None:
        query = query.where(LearningSessionModel.accuracy <= max_accuracy)
    if created_from is not None:
        query = query.where(LearningSessionModel.created_at >= created_from)
    if created_to is not None:
        query = query.where(LearningSessionModel.created_at < created_to)
    return query


class TrainingRepository:
    def __init__(self, db: Session = Depends(get_db)) -> None:
        self._db = db

    def list_sessions_paginated(
        self,
        *,
        user_id: int,
        limit: int,
        offset: int,
        min_accuracy: float | None = None,
        max_accuracy: float | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[LearningSessionModel]:
        query = select(LearningSessionModel)
        query = _apply_session_filters(
            query,
            user_id=user_id,
            min_accuracy=min_accuracy,
            max_accuracy=max_accuracy,
            created_from=created_from,
            created_to=created_to,
        )
        query = query.order_by(LearningSessionModel.id.desc()).limit(limit).offset(offset)
        return list(self._db.scalars(query))

    def count_sessions(
        self,
        *,
        user_id: int,
        min_accuracy: float | None = None,
        max_accuracy: float | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        query = select(func.count(LearningSessionModel.id))
        query = _apply_session_filters(
            query,
            user_id=user_id,
            min_accuracy=min_accuracy,
            max_accuracy=max_accuracy,
            created_from=created_from,
            created_to=created_to,
        )
        return int(self._db.scalar(query) or 0)

    def list_answers_by_session(self, session_id: int, user_id: int) -> list[AnswerModel] | None:
        session_row = self._db.scalar(
            select(LearningSessionModel).where(
                LearningSessionModel.id == session_id,
                LearningSessionModel.user_id == user_id,
            )
        )
        if session_row is None:
            return None
        return list(self._db.scalars(
            select(AnswerModel)
            .where(AnswerModel.session_id == session_id)
            .order_by(AnswerModel.id.asc())
        ))

    def create_session_with_answers(
        self,
        user_id: int,
        total: int,
        correct: int,
        accuracy: float,
        answers: list[AnswerPersistPayload],
        *,
        auto_commit: bool = True,
    ) -> LearningSessionModel:
        session_row = LearningSessionModel(
            user_id=user_id,
            total=total,
            correct=correct,
            accuracy=accuracy,
        )
        self._db.add(session_row)
        self._db.flush()

        for answer in answers:
            self._db.add(
                AnswerModel(
                    session_id=session_row.id,
                    exercise_id=answer.exercise_id,
                    exercise_type=answer.exercise_type,
                    target_word=answer.target_word,
                    prompt=answer.prompt,
                    expected_answer=answer.expected_answer,
                    user_answer=answer.user_answer,
                    is_correct=answer.is_correct,
                )
            )

        if auto_commit:
            self._db.commit()
        else:
            self._db.flush()
        self._db.refresh(session_row)
        return session_row

    def list_recent_incorrect_answer_data(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[tuple[str | None, str | None]]:
        """Возвращает сырые пары (target_word, prompt) для неверных ответов."""
        rows = list(self._db.execute(
            select(
                AnswerModel.target_word,
                AnswerModel.prompt,
            )
            .join(LearningSessionModel, LearningSessionModel.id == AnswerModel.session_id)
            .where(
                LearningSessionModel.user_id == user_id,
                AnswerModel.is_correct.is_(False),
            )
            .order_by(AnswerModel.id.desc())
            .limit(limit)
        ))
        return [(row[0], row[1]) for row in rows]

    def get_progress_snapshot(self, *, user_id: int) -> tuple[int, float]:
        total = int(self._db.scalar(
            select(func.count(LearningSessionModel.id)).where(LearningSessionModel.user_id == user_id)
        ) or 0)
        avg = round(float(self._db.scalar(
            select(func.avg(LearningSessionModel.accuracy)).where(LearningSessionModel.user_id == user_id)
        ) or 0.0), 4)
        return total, avg
