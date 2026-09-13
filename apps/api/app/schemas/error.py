"""Consistent error envelope for future exception handling."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Safe, client-facing information about an API error."""

    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    """Foundation for future versioned API error responses."""

    error: ErrorDetail
