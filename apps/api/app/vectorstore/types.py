"""Typed vector provider inputs, results, and controlled failures."""

from dataclasses import dataclass
from typing import Any


class VectorStoreError(Exception):
    """Base vector-store failure."""


class VectorStoreUnavailableError(VectorStoreError):
    """The configured vector store cannot be reached or used."""


@dataclass(frozen=True)
class VectorRecord:
    id: str
    values: list[float]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class VectorMatch:
    id: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IndexInfo:
    name: str
    dimension: int
    metric: str
    ready: bool
    vector_count: int | None = None
