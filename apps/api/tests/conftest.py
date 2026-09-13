"""Isolated SQLite fixtures shared by Phase 2 tests."""

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.base import Base
from app.database.models import User
from app.database.session import create_database_engine, get_db
from app.embeddings.factory import get_embedding_provider
from app.extraction.service import ExtractionService, get_extraction_service
from app.ingestion.parser import DocumentParser
from app.llm.factory import get_llm_provider
from app.main import app
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate
from app.services.document import DocumentService, get_document_service
from app.vectorstore.factory import get_vector_store_provider
from app.vectorstore.types import IndexInfo, VectorMatch, VectorRecord, VectorStoreUnavailableError


class UnavailableTestOCR:
    def is_available(self) -> bool:
        return False

    def extract_text(self, image_path: Path) -> str:
        raise AssertionError(f"OCR should not run for {image_path}")


class FakeLLMProvider:
    def __init__(self) -> None:
        self.available = True
        self.response: str = json.dumps(
            {
                "conditions": [],
                "medications": [],
                "labs": [],
                "symptoms": [],
                "measurements": [],
                "warnings": [],
                "document_date": None,
            }
        )
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def health_check(self) -> bool:
        return self.available

    def generate_structured(self, prompt: str, schema: dict[str, Any]) -> str:
        self.calls.append((prompt, schema))
        return self.response


class FakeEmbeddingProvider:
    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.available = True
        self.calls: list[list[str]] = []

    def health_check(self) -> bool:
        return self.available

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if not self.available:
            from app.embeddings.types import EmbeddingUnavailableError

            raise EmbeddingUnavailableError("fake unavailable")
        return [
            [
                float((sum(text.encode("utf-8")) + index) % 17) / 17
                for index in range(self.dimension)
            ]
            for text in texts
        ]


class FakeVectorStoreProvider:
    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.available = True
        self.records: dict[str, list[VectorRecord]] = {}
        self.query_profiles: list[str] = []
        self.deleted_documents: list[tuple[str, str]] = []

    def _require_available(self) -> None:
        if not self.available:
            raise VectorStoreUnavailableError("fake unavailable")

    def health_check(self) -> bool:
        return self.available

    def get_index_info(self) -> IndexInfo:
        self._require_available()
        return IndexInfo(
            name="fake-index",
            dimension=self.dimension,
            metric="cosine",
            ready=True,
            vector_count=sum(len(rows) for rows in self.records.values()),
        )

    def upsert_chunks(self, profile_id: str, chunks: list[VectorRecord]) -> int:
        self._require_available()
        existing = {row.id: row for row in self.records.get(profile_id, [])}
        existing.update({row.id: row for row in chunks})
        self.records[profile_id] = list(existing.values())
        return len(chunks)

    def query(self, profile_id: str, vector: list[float], top_k: int) -> list[VectorMatch]:
        del vector
        self._require_available()
        self.query_profiles.append(profile_id)
        return [
            VectorMatch(id=row.id, score=0.91 - index * 0.01, metadata=row.metadata)
            for index, row in enumerate(self.records.get(profile_id, [])[:top_k])
        ]

    def delete_document(self, document_id: str, profile_id: str) -> None:
        self._require_available()
        self.deleted_documents.append((document_id, profile_id))
        self.records[profile_id] = [
            row
            for row in self.records.get(profile_id, [])
            if row.metadata.get("document_id") != document_id
        ]

    def delete_profile(self, profile_id: str) -> None:
        self._require_available()
        self.records.pop(profile_id, None)


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    database_path = tmp_path / "test.db"
    test_engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(test_engine)
    with Session(test_engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def document_service(tmp_path: Path) -> DocumentService:
    settings = Settings(upload_dir=str(tmp_path / "uploads"))
    return DocumentService(
        settings=settings,
        parser=DocumentParser(ocr_provider=UnavailableTestOCR()),
    )


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def fake_vector_store() -> FakeVectorStoreProvider:
    return FakeVectorStoreProvider()


@pytest.fixture
def client(
    db_session: Session,
    document_service: DocumentService,
    fake_llm: FakeLLMProvider,
    fake_embeddings: FakeEmbeddingProvider,
    fake_vector_store: FakeVectorStoreProvider,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_document_service] = lambda: document_service
    app.dependency_overrides[get_extraction_service] = lambda: ExtractionService(fake_llm)
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    app.dependency_overrides[get_vector_store_provider] = lambda: fake_vector_store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user(db_session: Session) -> User:
    created = UserRepository().create(
        db_session, UserCreate(username="test-user", email="test@example.invalid")
    )
    db_session.commit()
    return created
