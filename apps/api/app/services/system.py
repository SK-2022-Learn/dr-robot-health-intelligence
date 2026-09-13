"""Safe system status without exposing paths, providers, or credentials."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.graph import graph_runtime_available
from app.config import Settings, get_settings
from app.database.session import REPOSITORY_ROOT
from app.embeddings.base import EmbeddingProvider
from app.embeddings.types import EmbeddingError
from app.llm.base import LLMProvider
from app.repositories.system import SystemRepository
from app.safety.policy import POLICY_VERSION
from app.schemas.system import SystemStatusRead
from app.vectorstore.base import VectorStoreProvider
from app.vectorstore.types import VectorStoreError


class SystemService:
    def __init__(
        self,
        repository: SystemRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository or SystemRepository()
        self.settings = settings or get_settings()

    def status(
        self,
        db: Session,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStoreProvider,
    ) -> SystemStatusRead:
        upload_path = Path(self.settings.upload_dir)
        if not upload_path.is_absolute():
            upload_path = REPOSITORY_ROOT / upload_path
        vector_info = None
        embedding_dimension = None
        try:
            vector_info = vector_store.get_index_info()
        except VectorStoreError:
            pass
        try:
            embedding_dimension = len(embedding_provider.embed_text("dimension check"))
        except EmbeddingError:
            pass
        compatibility = "unavailable"
        if vector_info is not None and embedding_dimension is not None:
            compatibility = (
                "compatible"
                if vector_info.dimension == embedding_dimension
                else "dimension_mismatch"
            )
        return SystemStatusRead(
            environment=self.settings.app_env,
            database="connected" if self.repository.database_available(db) else "unavailable",
            upload_directory="configured" if upload_path.is_dir() else "unavailable",
            vector_status=(
                "connected" if vector_info is not None and vector_info.ready else "unavailable"
            ),
            vector_index=self.settings.pinecone_index or "Not configured",
            vector_dimension=vector_info.dimension if vector_info is not None else None,
            vector_metric=vector_info.metric if vector_info is not None else None,
            vector_count=vector_info.vector_count if vector_info is not None else None,
            embedding_model=self.settings.ollama_embedding_model or "Not configured",
            embedding_status="connected" if embedding_dimension is not None else "unavailable",
            embedding_dimension=embedding_dimension,
            compatibility=compatibility,
            llm_model=self.settings.ollama_model or "Not configured",
            llm="connected" if llm_provider.health_check() else "unavailable",
            safety_policy_version=POLICY_VERSION,
            agent_orchestration=("enabled" if graph_runtime_available() else "unavailable"),
        )
