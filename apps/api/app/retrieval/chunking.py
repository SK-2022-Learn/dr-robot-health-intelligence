"""Deterministic, page-aware text chunking with overlap."""

from hashlib import sha256

from app.database.models import DocumentPage, SourceDocument
from app.retrieval.types import DocumentChunk


def _chunk_id(profile_id: str, document_id: str, page_number: int, chunk_index: int) -> str:
    return f"{profile_id}:{document_id}:{page_number}:{chunk_index}"


def chunk_document_pages(
    document: SourceDocument,
    pages: list[DocumentPage],
    *,
    chunk_size: int,
    overlap: int,
) -> list[DocumentChunk]:
    if overlap >= chunk_size:
        raise ValueError("Chunk overlap must be smaller than chunk size.")
    chunks: list[DocumentChunk] = []
    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        start = 0
        chunk_index = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + chunk_size // 2, end)
                if boundary > start:
                    end = boundary
            chunk_text = text[start:end].strip()
            if chunk_text:
                digest = sha256(chunk_text.encode("utf-8")).hexdigest()
                chunks.append(
                    DocumentChunk(
                        chunk_id=_chunk_id(
                            document.profile_id,
                            document.id,
                            page.page_number,
                            chunk_index,
                        ),
                        document_id=document.id,
                        profile_id=document.profile_id,
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        text_hash=digest,
                        start_offset=start,
                        end_offset=end,
                        metadata={
                            "profile_id": document.profile_id,
                            "document_id": document.id,
                            "page_number": page.page_number,
                            "chunk_index": chunk_index,
                            "document_type": document.mime_type,
                            "original_filename": document.original_filename,
                            "provenance": "SOURCE_DOCUMENT",
                            "text_hash": digest,
                            "start_offset": start,
                            "end_offset": end,
                        },
                    )
                )
                chunk_index += 1
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks
