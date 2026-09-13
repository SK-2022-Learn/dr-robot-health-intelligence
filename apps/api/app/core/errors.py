"""Consistent client-safe error envelope for domain failures."""

from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from app.schemas.error import ErrorDetail, ErrorResponse


class ApiError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    """Return a stable envelope without exposing stack traces or internal data."""

    response = ErrorResponse(
        error=ErrorDetail(code=exc.code, message=exc.message, request_id=str(uuid4()))
    )
    return JSONResponse(status_code=exc.status_code, content=response.model_dump())
