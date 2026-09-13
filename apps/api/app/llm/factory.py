"""Construct the configured language-model provider."""

from app.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.providers.ollama import OllamaProvider


def create_llm_provider(configured: Settings) -> LLMProvider:
    if configured.llm_provider.lower() != "ollama":
        return UnavailableLLMProvider()
    return OllamaProvider(
        base_url=configured.ollama_base_url,
        model=configured.ollama_model,
        timeout_seconds=configured.ollama_timeout_seconds,
    )


def get_llm_provider() -> LLMProvider:
    return create_llm_provider(get_settings())


class UnavailableLLMProvider:
    def health_check(self) -> bool:
        return False

    def generate_structured(self, prompt: str, schema: dict[str, object]) -> str:
        del prompt, schema
        from app.llm.types import LLMUnavailableError

        raise LLMUnavailableError("The configured language-model provider is unavailable.")
