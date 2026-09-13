"""Phase 6 deterministic chunking, indexing, and retrieval tests."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.enums import VectorIndexStatus
from app.database.models import (
    AuditLog,
    DocumentPage,
    ExtractedCandidate,
    HealthEvent,
    Medication,
    Observation,
    SourceDocument,
    Symptom,
    User,
)
from app.embeddings.factory import create_embedding_provider
from app.retrieval.chunking import chunk_document_pages
from app.vectorstore.factory import create_vector_store_provider
from tests.conftest import FakeEmbeddingProvider, FakeVectorStoreProvider


def make_document(document_id: str = "document-a", profile_id: str = "profile-a") -> SourceDocument:
    return SourceDocument(
        id=document_id,
        profile_id=profile_id,
        original_filename="synthetic.txt",
        stored_filename=f"{document_id}.txt",
        mime_type="text/plain",
        storage_path=f"uploads/{document_id}.txt",
    )


def test_chunking_short_empty_and_multiple_pages() -> None:
    document = make_document()
    pages = [
        DocumentPage(document_id=document.id, page_number=1, text="Short page text."),
        DocumentPage(document_id=document.id, page_number=2, text="   "),
        DocumentPage(document_id=document.id, page_number=3, text="Another source page."),
    ]

    chunks = chunk_document_pages(document, pages, chunk_size=1200, overlap=200)

    assert [chunk.page_number for chunk in chunks] == [1, 3]
    assert [chunk.chunk_index for chunk in chunks] == [0, 0]
    assert chunks[0].text == "Short page text."
    assert len(chunks[0].text_hash) == 64
    assert chunks[0].chunk_id == "profile-a:document-a:1:0"


def test_chunking_long_page_overlap_and_ids_are_stable() -> None:
    document = make_document()
    page = DocumentPage(
        document_id=document.id,
        page_number=4,
        text=" ".join(f"word-{index:03d}" for index in range(100)),
    )

    first = chunk_document_pages(document, [page], chunk_size=220, overlap=40)
    second = chunk_document_pages(document, [page], chunk_size=220, overlap=40)

    assert len(first) > 1
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.text_hash for chunk in first] == [chunk.text_hash for chunk in second]
    assert first[1].start_offset < first[0].end_offset
    assert all(chunk.page_number == 4 for chunk in first)


def create_profile(client: TestClient, user: User, name: str) -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "owner_user_id": user.id,
            "display_name": name,
            "relationship_to_owner": "SELF" if name == "Profile A" else "OTHER",
            "access_level": "PRIVATE",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def upload(client: TestClient, profile_id: str, filename: str, text: str) -> str:
    response = client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={"file": (filename, text.encode(), "text/plain")},
        data={"document_date": "2026-09-01"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def trusted_counts(db: Session) -> tuple[int, int, int, int]:
    return tuple(
        int(db.scalar(select(func.count(model.id))) or 0)
        for model in (HealthEvent, Observation, Medication, Symptom)
    )


def test_index_and_reindex_preserve_sqlite_health_memory(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_vector_store: FakeVectorStoreProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    document_id = upload(
        client,
        profile_id,
        "diabetes.txt",
        "Synthetic Diabetes Follow-up\nFasting glucose: 118 mg/dL\nHbA1c: 7.2%",
    )
    before = trusted_counts(db_session)

    response = client.post(f"/api/v1/documents/{document_id}/index")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "document_id": document_id,
        "status": "INDEXED",
        "chunk_count": 1,
    }
    assert trusted_counts(db_session) == before
    document = db_session.get(SourceDocument, document_id)
    assert document is not None
    assert document.vector_index_status == VectorIndexStatus.INDEXED
    assert document.vector_indexed_at is not None
    assert document.vector_chunk_count == 1
    record = fake_vector_store.records[profile_id][0]
    assert record.id == f"{profile_id}:{document_id}:1:0"
    assert record.metadata["profile_id"] == profile_id
    assert record.metadata["document_id"] == document_id
    assert record.metadata["page_number"] == 1
    assert record.metadata["text_hash"]

    repeated = client.post(f"/api/v1/documents/{document_id}/index")
    assert repeated.status_code == 200
    assert fake_vector_store.deleted_documents == [
        (document_id, profile_id),
        (document_id, profile_id),
    ]
    assert len(fake_vector_store.records[profile_id]) == 1
    assert trusted_counts(db_session) == before
    actions = db_session.scalars(select(AuditLog.action)).all()
    assert actions.count("DOCUMENT_INDEXING_STARTED") == 2
    assert actions.count("DOCUMENT_INDEXING_COMPLETED") == 2


def test_dimension_mismatch_and_provider_failure_are_controlled(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_vector_store: FakeVectorStoreProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    document_id = upload(client, profile_id, "mismatch.txt", "Fasting glucose 118 mg/dL")
    fake_vector_store.dimension = 4

    mismatch = client.post(f"/api/v1/documents/{document_id}/index")

    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "VECTOR_DIMENSION_MISMATCH"
    document = db_session.get(SourceDocument, document_id)
    assert document is not None and document.vector_index_status == VectorIndexStatus.INDEX_FAILED
    assert db_session.scalar(select(func.count(ExtractedCandidate.id))) == 0

    fake_vector_store.dimension = 3
    fake_vector_store.available = False
    unavailable = client.post(f"/api/v1/documents/{document_id}/index")
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "VECTOR_STORE_UNAVAILABLE"


def test_embedding_failure_is_controlled(
    client: TestClient,
    user: User,
    fake_embeddings: FakeEmbeddingProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    document_id = upload(client, profile_id, "embedding.txt", "HbA1c 7.2 percent")
    fake_embeddings.available = False

    response = client.post(f"/api/v1/documents/{document_id}/index")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EMBEDDING_PROVIDER_UNAVAILABLE"


def test_semantic_search_validation_traceability_and_score(
    client: TestClient,
    db_session: Session,
    user: User,
    fake_vector_store: FakeVectorStoreProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    document_id = upload(client, profile_id, "glucose.txt", "Fasting glucose: 118 mg/dL")

    empty_before_index = client.post(
        f"/api/v1/profiles/{profile_id}/retrieval/search",
        json={"query": "glucose", "top_k": 5},
    )
    assert empty_before_index.status_code == 200
    assert empty_before_index.json()["indexed_document_count"] == 0
    assert empty_before_index.json()["results"] == []

    assert client.post(f"/api/v1/documents/{document_id}/index").status_code == 200
    response = client.post(
        f"/api/v1/profiles/{profile_id}/retrieval/search",
        json={"query": "What do my records say about glucose?", "top_k": 1},
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["score"] == pytest.approx(0.91)
    assert result["similarity_label"] == "retrieval similarity"
    assert result["document_id"] == document_id
    assert result["filename"] == "glucose.txt"
    assert result["page_number"] == 1
    assert result["text"] == "Fasting glucose: 118 mg/dL"
    assert fake_vector_store.query_profiles == [profile_id]
    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "SEMANTIC_SEARCH_EXECUTED"))
    assert audit is not None
    assert "glucose" not in str(audit.after_state).lower()

    assert (
        client.post(
            f"/api/v1/profiles/{profile_id}/retrieval/search", json={"query": "   "}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/profiles/{profile_id}/retrieval/search",
            json={"query": "glucose", "top_k": 21},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/profiles/missing/retrieval/search", json={"query": "glucose"}
        ).status_code
        == 404
    )


def test_critical_profile_isolation(
    client: TestClient,
    user: User,
    fake_vector_store: FakeVectorStoreProvider,
) -> None:
    profile_a = create_profile(client, user, "Profile A")
    profile_b = create_profile(client, user, "Profile B")
    document_a = upload(client, profile_a, "diabetes-a.txt", "Fasting glucose 118 mg/dL")
    document_b = upload(client, profile_b, "thyroid-b.txt", "Thyroid result TSH 4.8 mIU/L")
    assert client.post(f"/api/v1/documents/{document_a}/index").status_code == 200
    assert client.post(f"/api/v1/documents/{document_b}/index").status_code == 200

    search_a = client.post(
        f"/api/v1/profiles/{profile_a}/retrieval/search",
        json={"query": "thyroid", "top_k": 5},
    )
    search_b = client.post(
        f"/api/v1/profiles/{profile_b}/retrieval/search",
        json={"query": "glucose", "top_k": 5},
    )

    assert {row["document_id"] for row in search_a.json()["results"]} == {document_a}
    assert {row["document_id"] for row in search_b.json()["results"]} == {document_b}
    assert fake_vector_store.query_profiles == [profile_a, profile_b]


def test_missing_local_source_is_excluded_and_delete_profile_is_scoped(
    client: TestClient,
    user: User,
    fake_vector_store: FakeVectorStoreProvider,
) -> None:
    profile_id = create_profile(client, user, "Profile A")
    document_id = upload(client, profile_id, "source.txt", "Traceable glucose evidence")
    assert client.post(f"/api/v1/documents/{document_id}/index").status_code == 200
    record = fake_vector_store.records[profile_id][0]
    record.metadata["document_id"] = "missing"

    response = client.post(
        f"/api/v1/profiles/{profile_id}/retrieval/search",
        json={"query": "glucose"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []
    fake_vector_store.delete_profile(profile_id)
    assert profile_id not in fake_vector_store.records


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_PINECONE_TEST") != "1",
    reason="Set RUN_LIVE_PINECONE_TEST=1 to run live compatibility validation.",
)
def test_optional_live_pinecone_compatibility() -> None:
    settings = Settings()
    assert settings.pinecone_api_key and settings.pinecone_index
    vector_store = create_vector_store_provider(settings)
    embeddings = create_embedding_provider(settings)
    info = vector_store.get_index_info()
    assert info.ready
    assert info.dimension == len(embeddings.embed_text("live compatibility probe"))
