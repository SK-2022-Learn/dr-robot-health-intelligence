"""Read-only, non-sensitive system status."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import get_embedding_provider
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.schemas.system import SystemStatusRead
from app.services.system import SystemService
from app.vectorstore.base import VectorStoreProvider
from app.vectorstore.factory import get_vector_store_provider

router = APIRouter(tags=["system"])
service = SystemService()


@router.get("/system", response_model=SystemStatusRead)
def system_status(
    db: Annotated[Session, Depends(get_db)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    vector_store: Annotated[VectorStoreProvider, Depends(get_vector_store_provider)],
) -> SystemStatusRead:
    return service.status(db, llm_provider, embedding_provider, vector_store)
