"""Complete v1 service health with optional-subsystem degradation."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.graph import graph_runtime_available
from app.config import get_settings
from app.database.session import REPOSITORY_ROOT, get_db
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import get_embedding_provider
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.schemas.health import HealthChecks, HealthResponse
from app.vectorstore.base import VectorStoreProvider
from app.vectorstore.factory import get_vector_store_provider

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    db: Annotated[Session, Depends(get_db)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    vector_store: Annotated[VectorStoreProvider, Depends(get_vector_store_provider)],
) -> HealthResponse:
    """Report API and lightweight relational database availability."""

    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except SQLAlchemyError:
        database_status = "unavailable"
        db.rollback()

    settings = get_settings()
    upload_path = Path(settings.upload_dir)
    if not upload_path.is_absolute():
        upload_path = REPOSITORY_ROOT / upload_path
    checks = HealthChecks(
        api="ok",
        database=database_status,
        llm="ok" if llm_provider.health_check() else "unavailable",
        embedding="ok" if embedding_provider.health_check() else "unavailable",
        vector_database="ok" if vector_store.health_check() else "unavailable",
        upload_storage="ok" if upload_path.is_dir() else "unavailable",
        safety="ok",
        agent_graph="ok" if graph_runtime_available() else "unavailable",
    )

    return HealthResponse(
        status=(
            "ok" if all(value == "ok" for value in checks.model_dump().values()) else "degraded"
        ),
        checks=checks,
    )
