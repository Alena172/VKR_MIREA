from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.learning.models.session_models import LearningSessionAnswerModel, LearningSessionModel


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
    explanation_ru: str | None


class LearningSessionRepository:
    """Запросы к учебным сессиям и ответам пользователя."""

    def _apply_session_filters(
        self,
        query: Select,
        *,
        user_id: int | None,
        min_accuracy: float | None = None,
        max_accuracy: float | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> Select:
        """Применяет общие фильтры истории сессий к SQLAlchemy-запросу."""

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

    def list_sessions(self, db: Session, user_id: int | None) -> list[LearningSessionModel]:
        query = select(LearningSessionModel)
        query = self._apply_session_filters(query, user_id=user_id)
        query = query.order_by(LearningSessionModel.id.desc())
        return list(db.scalars(query))

    def list_sessions_paginated(
        self,
        db: Session,
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
        query = self._apply_session_filters(
            query,
            user_id=user_id,
            min_accuracy=min_accuracy,
            max_accuracy=max_accuracy,
            created_from=created_from,
            created_to=created_to,
        )
        query = query.order_by(LearningSessionModel.id.desc()).limit(limit).offset(offset)
        return list(db.scalars(query))

    def count_sessions(
        self,
        db: Session,
        *,
        user_id: int,
        min_accuracy: float | None = None,
        max_accuracy: float | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        query = select(func.count(LearningSessionModel.id))
        query = self._apply_session_filters(
            query,
            user_id=user_id,
            min_accuracy=min_accuracy,
            max_accuracy=max_accuracy,
            created_from=created_from,
            created_to=created_to,
        )
        return int(db.scalar(query) or 0)

    def list_answers_by_session(
        self,
        db: Session,
        session_id: int,
        user_id: int,
    ) -> list[LearningSessionAnswerModel] | None:
        session_query = select(LearningSessionModel).where(
            LearningSessionModel.id == session_id,
            LearningSessionModel.user_id == user_id,
        )
        session_row = db.scalar(session_query)
        if session_row is None:
            return None

        answers_query = (
            select(LearningSessionAnswerModel)
            .where(LearningSessionAnswerModel.session_id == session_id)
            .order_by(LearningSessionAnswerModel.id.asc())
        )
        return list(db.scalars(answers_query))

    def create_with_answers(
        self,
        db: Session,
        user_id: int,
        total: int,
        correct: int,
        accuracy: float,
        answers: list[AnswerPersistPayload],
        *,
        auto_commit: bool = True,
    ) -> LearningSessionModel:
        """Создает сессию и сохраняет все ответы одним блоком."""

        session_row = LearningSessionModel(
            user_id=user_id,
            total=total,
            correct=correct,
            accuracy=accuracy,
        )
        db.add(session_row)
        db.flush()

        for answer in answers:
            db.add(
                LearningSessionAnswerModel(
                    session_id=session_row.id,
                    exercise_id=answer.exercise_id,
                    exercise_type=answer.exercise_type,
                    target_word=answer.target_word,
                    prompt=answer.prompt,
                    expected_answer=answer.expected_answer,
                    user_answer=answer.user_answer,
                    is_correct=answer.is_correct,
                    explanation_ru=answer.explanation_ru,
                )
            )

        if auto_commit:
            db.commit()
            db.refresh(session_row)
        else:
            db.flush()
        return session_row

    def list_recent_incorrect_words(
        self,
        db: Session,
        user_id: int,
        limit: int = 20,
        unique: bool = True,
    ) -> list[str]:
        """Возвращает последние слова, по которым пользователь ошибался."""

        query = (
            select(
                LearningSessionAnswerModel.target_word,
                LearningSessionAnswerModel.prompt,
            )
            .join(
                LearningSessionModel,
                LearningSessionModel.id == LearningSessionAnswerModel.session_id,
            )
            .where(
                LearningSessionModel.user_id == user_id,
                LearningSessionAnswerModel.is_correct.is_(False),
            )
            .order_by(LearningSessionAnswerModel.id.desc())
            .limit(limit)
        )
        rows = list(db.execute(query))

        words: list[str] = []
        for target_word, prompt in rows:
            word = (target_word or "").strip().lower()
            if not word:
                prompt_text = (prompt or "").strip()
                if not prompt_text:
                    continue
                word = prompt_text.split(":", maxsplit=1)[-1].strip().lower()
            if not word:
                continue
            if unique:
                if word not in words:
                    words.append(word)
            else:
                words.append(word)
        return words

    def get_progress_snapshot(self, db: Session, *, user_id: int) -> tuple[int, float]:
        total_stmt = select(func.count(LearningSessionModel.id)).where(LearningSessionModel.user_id == user_id)
        avg_stmt = select(func.avg(LearningSessionModel.accuracy)).where(LearningSessionModel.user_id == user_id)
        total = int(db.scalar(total_stmt) or 0)
        avg = round(float(db.scalar(avg_stmt) or 0.0), 4)
        return total, avg


learning_session_repository = LearningSessionRepository()
