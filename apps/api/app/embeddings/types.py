"""Controlled embedding provider failures."""


class EmbeddingError(Exception):
    """Base exception safe for service-layer classification."""


class EmbeddingUnavailableError(EmbeddingError):
    """The configured embedding provider cannot be reached or used."""


class EmbeddingResponseError(EmbeddingError):
    """The provider returned an invalid embedding response."""
