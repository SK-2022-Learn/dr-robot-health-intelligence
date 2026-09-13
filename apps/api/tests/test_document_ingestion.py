"""Phase 4 document ingestion, isolation, parsing, and audit tests."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import HealthEvent, SourceDocument, User
from app.ingestion.types import DocumentParseError
from app.services.document import DocumentService


def create_profile(client: TestClient, user: User, name: str = "Upload profile") -> str:
    response = client.post(
        "/api/v1/profiles",
        json={
            "owner_user_id": user.id,
            "display_name": name,
            "relationship_to_owner": "SELF",
            "access_level": "PRIVATE",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def upload(
    client: TestClient,
    profile_id: str,
    filename: str,
    content: bytes,
    mime_type: str,
):
    return client.post(
        f"/api/v1/profiles/{profile_id}/documents",
        files={"file": (filename, content, mime_type)},
    )


def synthetic_pdf(*page_text: str) -> bytes:
    document = pymupdf.open()
    for text in page_text:
        page = document.new_page()
        page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


def synthetic_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (24, 24), color="white").save(output, format="PNG")
    return output.getvalue()


def test_txt_upload_storage_hash_reads_audit_and_no_health_event(
    client: TestClient,
    db_session: Session,
    user: User,
    document_service: DocumentService,
) -> None:
    profile_id = create_profile(client, user)
    content = b"Synthetic record line one.\nSynthetic record line two."
    before_events = db_session.scalar(select(func.count(HealthEvent.id)))

    response = upload(client, profile_id, "synthetic-record.txt", content, "text/plain")

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "synthetic-record.txt"
    assert body["mime_type"] == "text/plain"
    assert body["status"] == "PARSED"
    assert body["page_count"] == 1
    assert body["has_extracted_text"] is True
    assert "storage_path" not in body
    assert "extracted_text" not in body

    row = db_session.get(SourceDocument, body["id"])
    assert row is not None
    assert row.file_hash == sha256(content).hexdigest()
    assert row.stored_filename == f"{row.id}.txt"
    assert row.original_filename == "synthetic-record.txt"
    assert row.storage_path == f"{profile_id}/{row.id}.txt"
    assert (document_service.storage.root / row.storage_path).read_bytes() == content
    assert db_session.scalar(select(func.count(HealthEvent.id))) == before_events

    listing = client.get(f"/api/v1/profiles/{profile_id}/documents")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == row.id
    detail = client.get(f"/api/v1/documents/{row.id}")
    assert detail.status_code == 200
    assert detail.json()["has_extracted_text"] is True
    assert "storage_path" not in detail.json()
    pages = client.get(f"/api/v1/documents/{row.id}/pages")
    assert pages.status_code == 200
    assert pages.json()[0]["page_number"] == 1
    assert pages.json()[0]["text"] == content.decode()

    audit = client.get("/api/v1/audit", params={"entity_id": row.id})
    assert {entry["action"] for entry in audit.json()} == {
        "DOCUMENT_UPLOADED",
        "DOCUMENT_PARSED",
    }
    assert all("extracted_text" not in (entry["after_state"] or {}) for entry in audit.json())
    assert all(content.decode() not in str(entry) for entry in audit.json())


def test_pdf_upload_extracts_page_level_text(client: TestClient, user: User) -> None:
    profile_id = create_profile(client, user)
    response = upload(
        client,
        profile_id,
        "synthetic.pdf",
        synthetic_pdf("Synthetic first page", "Synthetic second page"),
        "application/pdf",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "PARSED"
    assert response.json()["page_count"] == 2
    pages = client.get(f"/api/v1/documents/{response.json()['id']}/pages").json()
    assert [page["page_number"] for page in pages] == [1, 2]
    assert "Synthetic first page" in pages[0]["text"]
    assert "Synthetic second page" in pages[1]["text"]


def test_valid_image_is_stored_and_needs_ocr(
    client: TestClient, user: User, document_service: DocumentService
) -> None:
    profile_id = create_profile(client, user)
    response = upload(client, profile_id, "scan.png", synthetic_png(), "image/png")

    assert response.status_code == 201
    assert response.json()["status"] == "NEEDS_OCR"
    document = db_document(document_service, response.json()["id"], profile_id, ".png")
    assert document.exists()


def db_document(
    document_service: DocumentService, document_id: str, profile_id: str, extension: str
) -> Path:
    return document_service.storage.root / profile_id / f"{document_id}{extension}"


@pytest.mark.parametrize(
    ("filename", "content", "mime_type", "code"),
    [
        ("bad.exe", b"binary", "application/octet-stream", "UNSUPPORTED_FILE_TYPE"),
        ("fake.pdf", b"plain text", "application/pdf", "UNSUPPORTED_FILE_TYPE"),
        ("fake.txt", b"plain text", "application/pdf", "UNSUPPORTED_FILE_TYPE"),
        ("empty.txt", b"", "text/plain", "EMPTY_FILE"),
    ],
)
def test_upload_validation_errors(
    client: TestClient,
    user: User,
    filename: str,
    content: bytes,
    mime_type: str,
    code: str,
) -> None:
    profile_id = create_profile(client, user)
    response = upload(client, profile_id, filename, content, mime_type)
    assert response.status_code in {413, 415, 422}
    assert response.json()["error"]["code"] == code


def test_oversized_upload_rejected(
    client: TestClient, user: User, document_service: DocumentService
) -> None:
    document_service.settings.max_upload_size_mb = 1
    profile_id = create_profile(client, user)
    response = upload(client, profile_id, "large.txt", b"x" * (1024 * 1024 + 1), "text/plain")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_invalid_profile_and_document_not_found(client: TestClient) -> None:
    invalid = upload(client, "missing", "synthetic.txt", b"content", "text/plain")
    assert invalid.status_code == 404
    assert invalid.json()["error"]["code"] == "PROFILE_NOT_FOUND"
    for suffix in ("", "/pages"):
        response = client.get(f"/api/v1/documents/missing{suffix}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_duplicate_is_profile_scoped(client: TestClient, user: User) -> None:
    first_profile = create_profile(client, user, "First")
    second_profile = create_profile(client, user, "Second")
    content = b"Same synthetic content"
    assert upload(client, first_profile, "first.txt", content, "text/plain").status_code == 201

    duplicate = upload(client, first_profile, "again.txt", content, "text/plain")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_DOCUMENT"
    assert upload(client, second_profile, "private.txt", content, "text/plain").status_code == 201


@pytest.mark.parametrize(
    ("malicious_name", "content"),
    [
        ("../../something.txt", b"posix traversal test"),
        ("..\\..\\something.txt", b"windows traversal test"),
    ],
)
def test_path_traversal_filename_stays_inside_profile_directory(
    client: TestClient,
    user: User,
    document_service: DocumentService,
    malicious_name: str,
    content: bytes,
) -> None:
    profile_id = create_profile(client, user)
    response = upload(client, profile_id, malicious_name, content, "text/plain")
    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "something.txt"
    stored = db_document(document_service, body["id"], profile_id, ".txt").resolve()
    assert stored.is_relative_to(document_service.storage.root.resolve())
    assert stored.exists()


def test_parse_failure_persists_evidence_and_failure_audit(
    client: TestClient,
    db_session: Session,
    user: User,
    document_service: DocumentService,
) -> None:
    class FailingParser:
        def parse(self, path: Path, mime_type: str):
            raise DocumentParseError(f"Synthetic failure for {path.suffix} {mime_type}")

    document_service.parser = FailingParser()  # type: ignore[assignment]
    profile_id = create_profile(client, user)
    response = upload(
        client,
        profile_id,
        "failure.pdf",
        synthetic_pdf("Synthetic failure fixture"),
        "application/pdf",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    row = db_session.get(SourceDocument, response.json()["id"])
    assert row is not None
    assert db_document(document_service, row.id, profile_id, ".pdf").exists()
    audit = client.get("/api/v1/audit", params={"entity_id": row.id}).json()
    assert {entry["action"] for entry in audit} == {
        "DOCUMENT_UPLOADED",
        "DOCUMENT_PARSE_FAILED",
    }
