from __future__ import annotations

from app.modules.exercise_engine.contracts import ExerciseGenerateResultDTO, ExerciseItemDTO
from app.modules.exercise_engine.schemas import ExerciseGenerateResponse, ExerciseItem


def to_exercise_item_dto(item: ExerciseItem) -> ExerciseItemDTO:
    return ExerciseItemDTO(
        prompt=item.prompt,
        answer=item.answer,
        exercise_type=item.exercise_type,
        options=list(item.options),
    )


def to_exercise_generate_result_dto(response: ExerciseGenerateResponse) -> ExerciseGenerateResultDTO:
    return ExerciseGenerateResultDTO(
        exercises=[to_exercise_item_dto(item) for item in response.exercises],
        note=response.note,
    )
