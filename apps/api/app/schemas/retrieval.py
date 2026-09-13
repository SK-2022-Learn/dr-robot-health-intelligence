"""Indexing and semantic-evidence API contracts."""

from typing import Literal

from pydantic import Field, field_validator

from app.database.enums import VectorIndexStatus
from app.schemas.common import SchemaModel


class DocumentIndexSummary(SchemaModel):
    document_id: str
    status: VectorIndexStatus
    chunk_count: int


class RetrievalSearchRequest(SchemaModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query must contain text.")
        return value


class EvidenceContext(SchemaModel):
    score: float
    similarity_label: Literal["retrieval similarity"] = "retrieval similarity"
    document_id: str
    filename: str
    page_number: int
    text: str
    chunk_index: int


class RetrievalSearchResponse(SchemaModel):
    query: str
    results: list[EvidenceContext]
    indexed_document_count: int
