"""Deterministic ambiguity detection and allowlisted clarification merging."""

from copy import deepcopy

from pydantic import ValidationError

from app.chat.schemas import (
    ClarificationQuestion,
    DailyHealthExtraction,
    GlucoseContext,
    GlucoseEntry,
    WeightEntry,
)
from app.core.errors import ApiError


def required_clarifications(
    extraction: DailyHealthExtraction,
) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    for index, observation in enumerate(extraction.observations):
        if isinstance(observation, GlucoseEntry) and observation.context == GlucoseContext.UNKNOWN:
            questions.append(
                ClarificationQuestion(
                    field=f"observations.{index}.context",
                    question="Was this reading fasting, before a meal, after a meal, or random?",
                    options=["FASTING", "BEFORE_MEAL", "AFTER_MEAL", "RANDOM"],
                )
            )
        if isinstance(observation, WeightEntry) and observation.unit is None:
            questions.append(
                ClarificationQuestion(
                    field=f"observations.{index}.unit",
                    question=f"Is that {observation.value:g} kg or {observation.value:g} lb?",
                    options=["kg", "lb"],
                )
            )
    return questions


def merge_clarification_answers(
    extraction: DailyHealthExtraction, answers: dict[str, str]
) -> DailyHealthExtraction:
    allowed = {question.field: question for question in required_clarifications(extraction)}
    if not answers or any(field not in allowed for field in answers):
        raise ApiError(
            status_code=422,
            code="INVALID_CLARIFICATION_FIELD",
            message="A clarification answer referenced an unsupported field.",
        )
    payload = deepcopy(extraction.model_dump(mode="json"))
    for field, answer in answers.items():
        question = allowed[field]
        if answer not in question.options:
            raise ApiError(
                status_code=422,
                code="INVALID_CLARIFICATION_ANSWER",
                message="A clarification answer was not one of the allowed options.",
            )
        _, index_text, attribute = field.split(".")
        payload["observations"][int(index_text)][attribute] = answer
    try:
        updated = DailyHealthExtraction.model_validate(payload)
    except (ValidationError, ValueError, IndexError) as error:
        raise ApiError(
            status_code=422,
            code="INVALID_CLARIFICATION_ANSWER",
            message="Clarification answers could not be applied safely.",
        ) from error
    updated.clarifications = required_clarifications(updated)
    return updated
