"""Plain-text parsing without interpretation."""

from pathlib import Path

from app.database.enums import DocumentStatus
from app.ingestion.types import DocumentParseError, ParsedDocument, ParsedPage


class TextParser:
    def parse(self, path: Path) -> ParsedDocument:
        content = path.read_bytes()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = content.decode("windows-1252")
            except UnicodeDecodeError as exc:
                raise DocumentParseError("Text decoding failed.") from exc
        return ParsedDocument(
            full_text=text,
            pages=[ParsedPage(page_number=1, text=text)],
            status=DocumentStatus.PARSED,
        )
