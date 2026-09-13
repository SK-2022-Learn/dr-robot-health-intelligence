"""Contract tests for Phase 1 API endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.health import health


def test_root_metadata(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Dr. Robot",
        "status": "running",
        "environment": "development",
    }


def test_versioned_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "dr-robot-api",
        "version": "1.0.0",
        "checks": {
            "api": "ok",
            "database": "ok",
            "llm": "ok",
            "embedding": "ok",
            "vector_database": "ok",
            "upload_storage": "ok",
            "safety": "ok",
            "agent_graph": "ok",
        },
    }


def test_health_degrades_without_database() -> None:
    class BrokenSession:
        def execute(self, _: object) -> None:
            raise SQLAlchemyError("database unavailable")

        def rollback(self) -> None:
            pass

    class UnavailableProvider:
        def health_check(self) -> bool:
            return False

    unavailable = UnavailableProvider()
    response = health(  # type: ignore[arg-type]
        BrokenSession(), unavailable, unavailable, unavailable
    )

    assert response.status == "degraded"
    assert response.checks.database == "unavailable"
    assert response.checks.llm == "unavailable"
    assert response.checks.embedding == "unavailable"
    assert response.checks.vector_database == "unavailable"
