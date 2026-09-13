"""Select the appropriate raw parser for validated content."""

from pathlib import Path

from app.ingestion.ocr import OCRProvider, TesseractOCRProvider
from app.ingestion.parsers.image import ImageParser
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.text import TextParser
from app.ingestion.types import DocumentParseError, ParsedDocument


class DocumentParser:
    def __init__(self, ocr_provider: OCRProvider | None = None) -> None:
        self.pdf = PDFParser()
        self.text = TextParser()
        self.image = ImageParser(ocr_provider or TesseractOCRProvider())

    def parse(self, path: Path, mime_type: str) -> ParsedDocument:
        if mime_type == "application/pdf":
            return self.pdf.parse(path)
        if mime_type == "text/plain":
            return self.text.parse(path)
        if mime_type in {"image/png", "image/jpeg"}:
            return self.image.parse(path)
        raise DocumentParseError("No parser is configured for this document type.")
