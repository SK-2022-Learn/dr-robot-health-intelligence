"""Construct the configured vector store provider."""

from app.config import Settings, get_settings
from app.vectorstore.base import VectorStoreProvider
from app.vectorstore.providers.pinecone import PineconeProvider
from app.vectorstore.types import IndexInfo, VectorStoreUnavailableError


def create_vector_store_provider(configured: Settings) -> VectorStoreProvider:
    if configured.vector_provider.lower() != "pinecone":
        return UnavailableVectorStoreProvider()
    return PineconeProvider(
        api_key=configured.pinecone_api_key,
        index_name=configured.pinecone_index,
        namespace_prefix=configured.pinecone_namespace_prefix,
        timeout_seconds=configured.pinecone_timeout_seconds,
    )


def get_vector_store_provider() -> VectorStoreProvider:
    return create_vector_store_provider(get_settings())


class UnavailableVectorStoreProvider:
    def health_check(self) -> bool:
        return False

    def _raise(self) -> None:
        raise VectorStoreUnavailableError("The vector store provider is unavailable.")

    def upsert_chunks(self, profile_id: str, chunks: list) -> int:
        del profile_id, chunks
        self._raise()
        return 0

    def query(self, profile_id: str, vector: list[float], top_k: int) -> list:
        del profile_id, vector, top_k
        self._raise()
        return []

    def delete_document(self, document_id: str, profile_id: str) -> None:
        del document_id, profile_id
        self._raise()

    def delete_profile(self, profile_id: str) -> None:
        del profile_id
        self._raise()

    def get_index_info(self) -> IndexInfo:
        self._raise()
        raise AssertionError
