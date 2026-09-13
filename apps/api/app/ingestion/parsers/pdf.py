"""Text-layer PDF parsing with PyMuPDF."""

from pathlib import Path

import pymupdf

from app.database.enums import DocumentStatus
from app.ingestion.types import DocumentParseError, ParsedDocument, ParsedPage


class PDFParser:
    def parse(self, path: Path) -> ParsedDocument:
        try:
            with pymupdf.open(path) as document:
                pages = [
                    ParsedPage(page_number=index + 1, text=page.get_text("text"))
                    for index, page in enumerate(document)
                ]
        except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
            raise DocumentParseError("PDF parsing failed.") from exc
        combined = "\n\n".join(page.text for page in pages).strip()
        status = DocumentStatus.PARSED if len(combined) >= 3 else DocumentStatus.NEEDS_OCR
        return ParsedDocument(full_text=combined, pages=pages, status=status)
