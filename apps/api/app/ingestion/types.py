"""Internal ingestion value objects."""

from dataclasses import dataclass
from pathlib import Path

from app.database.enums import DocumentStatus


@dataclass(frozen=True)
class ValidatedUpload:
    original_filename: str
    extension: str
    mime_type: str
    content: bytes
    file_hash: str


@dataclass(frozen=True)
class StoredFile:
    stored_filename: str
    relative_path: str
    absolute_path: Path


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    full_text: str
    pages: list[ParsedPage]
    status: DocumentStatus

    @property
    def page_count(self) -> int:
        return len(self.pages)


class DocumentParseError(Exception):
    """Raised when raw text cannot be safely parsed from a supported document."""
