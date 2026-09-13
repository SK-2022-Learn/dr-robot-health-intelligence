"""Authoritative filename, size, declared-type, and content validation."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from app.core.errors import ApiError
from app.ingestion.types import ValidatedUpload

ALLOWED_FILE_TYPES: dict[str, tuple[str, str]] = {
    ".pdf": ("application/pdf", "pdf"),
    ".txt": ("text/plain", "text"),
    ".png": ("image/png", "png"),
    ".jpg": ("image/jpeg", "jpeg"),
    ".jpeg": ("image/jpeg", "jpeg"),
}


def safe_original_filename(filename: str) -> str:
    normalized = filename.strip().replace("\\", "/")
    basename = PurePosixPath(normalized).name
    if not basename or basename in {".", ".."} or "\x00" in basename:
        raise ApiError(status_code=422, code="INVALID_FILENAME", message="Filename is invalid.")
    if len(basename) > 255:
        raise ApiError(status_code=422, code="INVALID_FILENAME", message="Filename is too long.")
    return basename


def _validate_image(content: bytes, expected_format: str) -> None:
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
            actual_format = (image.format or "").lower()
    except (UnidentifiedImageError, OSError) as exc:
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message="Image content is invalid or does not match its declared type.",
        ) from exc
    if actual_format != expected_format:
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message="Image content does not match its filename and MIME type.",
        )


def _validate_content(content: bytes, kind: str) -> None:
    if kind == "pdf" and not content.startswith(b"%PDF-"):
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message="PDF content does not match its filename and MIME type.",
        )
    if kind == "text" and b"\x00" in content:
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message="Text uploads must contain plain text rather than binary content.",
        )
    if kind in {"png", "jpeg"}:
        _validate_image(content, kind)


def validate_upload(
    stream: BinaryIO,
    *,
    filename: str,
    declared_mime_type: str,
    max_size_bytes: int,
) -> ValidatedUpload:
    original_filename = safe_original_filename(filename)
    extension = PurePosixPath(original_filename).suffix.lower()
    configured = ALLOWED_FILE_TYPES.get(extension)
    normalized_mime = declared_mime_type.split(";", 1)[0].strip().lower()
    if configured is None or normalized_mime != configured[0]:
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message="Supported uploads are PDF, TXT, PNG, JPG, and JPEG.",
        )

    stream.seek(0)
    content = stream.read(max_size_bytes + 1)
    if not content:
        raise ApiError(status_code=422, code="EMPTY_FILE", message="The uploaded file is empty.")
    if len(content) > max_size_bytes:
        raise ApiError(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"The uploaded file exceeds the {max_size_bytes // (1024 * 1024)} MB limit.",
        )
    _validate_content(content, configured[1])
    return ValidatedUpload(
        original_filename=original_filename,
        extension=extension,
        mime_type=configured[0],
        content=content,
        file_hash=sha256(content).hexdigest(),
    )
