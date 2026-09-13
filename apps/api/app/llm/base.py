"""Provider contract used by extraction and health checks."""

from typing import Any, Protocol


class LLMProvider(Protocol):
    """Small interface that keeps business logic independent of Ollama."""

    def health_check(self) -> bool: ...

    def generate_structured(self, prompt: str, schema: dict[str, Any]) -> str: ...
