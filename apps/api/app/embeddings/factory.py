"""Construct the configured embedding provider."""

from app.config import Settings, get_settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.providers.ollama import OllamaEmbeddingProvider
from app.embeddings.types import EmbeddingUnavailableError


def create_embedding_provider(configured: Settings) -> EmbeddingProvider:
    if configured.embedding_provider.lower() != "ollama":
        return UnavailableEmbeddingProvider()
    return OllamaEmbeddingProvider(
        base_url=configured.ollama_base_url,
        model=configured.ollama_embedding_model,
        timeout_seconds=configured.embedding_timeout_seconds,
    )


def get_embedding_provider() -> EmbeddingProvider:
    return create_embedding_provider(get_settings())


class UnavailableEmbeddingProvider:
    def health_check(self) -> bool:
        return False

    def embed_text(self, text: str) -> list[float]:
        del text
        raise EmbeddingUnavailableError("The embedding provider is unavailable.")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise EmbeddingUnavailableError("The embedding provider is unavailable.")
