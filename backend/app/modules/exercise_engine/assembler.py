from __future__ import annotations

from app.modules.exercise_engine.contracts import ExerciseGenerateResultDTO, ExerciseItemDTO


def to_exercise_item_dto(
    *,
    prompt: str,
    answer: str,
    exercise_type: str,
    target_word: str | None,
    options: list[str],
) -> ExerciseItemDTO:
    return ExerciseItemDTO(
        prompt=prompt,
        answer=answer,
        exercise_type=exercise_type,
        target_word=target_word,
        options=list(options),
    )


def to_exercise_generate_result_dto(
    *,
    exercises: list[ExerciseItemDTO],
    note: str,
) -> ExerciseGenerateResultDTO:
    return ExerciseGenerateResultDTO(
        exercises=list(exercises),
        note=note,
    )
