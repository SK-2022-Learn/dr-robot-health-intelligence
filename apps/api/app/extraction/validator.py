"""Model-output JSON and Pydantic validation."""

from pydantic import ValidationError

from app.extraction.schemas import DocumentExtractionResult
from app.llm.types import LLMResponseError


def validate_extraction(raw_response: str) -> DocumentExtractionResult:
    try:
        return DocumentExtractionResult.model_validate_json(raw_response)
    except ValidationError as error:
        raise LLMResponseError("Structured output did not match the extraction schema.") from error
