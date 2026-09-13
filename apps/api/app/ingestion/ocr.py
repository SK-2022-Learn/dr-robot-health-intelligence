"""Replaceable OCR interface and optional local Tesseract implementation."""

from pathlib import Path
from shutil import which
from subprocess import CalledProcessError, TimeoutExpired, run
from typing import Protocol

from app.ingestion.types import DocumentParseError


class OCRProvider(Protocol):
    def is_available(self) -> bool: ...

    def extract_text(self, image_path: Path) -> str: ...


class TesseractOCRProvider:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or which("tesseract")

    def is_available(self) -> bool:
        return self.executable is not None

    def extract_text(self, image_path: Path) -> str:
        if self.executable is None:
            raise DocumentParseError("OCR provider is unavailable.")
        try:
            completed = run(
                [self.executable, str(image_path), "stdout", "--psm", "6"],
                capture_output=True,
                check=True,
                text=True,
                timeout=60,
            )
        except (CalledProcessError, OSError, TimeoutExpired) as exc:
            raise DocumentParseError("OCR processing failed.") from exc
        return completed.stdout
