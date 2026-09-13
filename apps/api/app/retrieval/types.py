"""Internal traceable document chunk structure."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    profile_id: str
    page_number: int
    chunk_index: int
    text: str
    text_hash: str
    start_offset: int
    end_offset: int
    metadata: dict[str, Any]
