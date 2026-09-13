"""Image parsing through an optional OCR provider."""

from pathlib import Path

from app.database.enums import DocumentStatus
from app.ingestion.ocr import OCRProvider
from app.ingestion.types import ParsedDocument, ParsedPage


class ImageParser:
    def __init__(self, ocr_provider: OCRProvider) -> None:
        self.ocr_provider = ocr_provider

    def parse(self, path: Path) -> ParsedDocument:
        if not self.ocr_provider.is_available():
            return ParsedDocument(
                full_text="",
                pages=[ParsedPage(page_number=1, text="")],
                status=DocumentStatus.NEEDS_OCR,
            )
        text = self.ocr_provider.extract_text(path).strip()
        if not text:
            return ParsedDocument(
                full_text="",
                pages=[ParsedPage(page_number=1, text="")],
                status=DocumentStatus.NEEDS_OCR,
            )
        return ParsedDocument(
            full_text=text,
            pages=[ParsedPage(page_number=1, text=text)],
            status=DocumentStatus.PARSED,
        )
