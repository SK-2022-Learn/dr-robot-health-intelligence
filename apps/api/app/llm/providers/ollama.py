"""Minimal Ollama HTTP provider with structured-output support."""

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.llm.types import LLMResponseError, LLMUnavailableError

UNSUPPORTED_GRAMMAR_KEYS = {
    "$defs",
    "default",
    "format",
    "maxLength",
    "maximum",
    "minLength",
    "minimum",
    "title",
}


def _ollama_grammar_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline references and remove annotations unsupported by Ollama's grammar parser.

    The original, complete Pydantic schema remains authoritative after generation.
    """

    definitions = schema.get("$defs", {})

    def clean(value: Any) -> Any:
        if isinstance(value, list):
            return [clean(item) for item in value]
        if not isinstance(value, dict):
            return value
        reference = value.get("$ref")
        if isinstance(reference, str):
            definition = definitions.get(reference.rsplit("/", maxsplit=1)[-1])
            if isinstance(definition, dict):
                return clean(definition)
        return {
            key: clean(item) for key, item in value.items() if key not in UNSUPPORTED_GRAMMAR_KEYS
        }

    return clean(schema)


class OllamaProvider:
    def __init__(self, *, base_url: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def health_check(self) -> bool:
        if not self.model:
            return False
        request = Request(f"{self.base_url}/api/tags", headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=min(self.timeout_seconds, 5.0)) as response:  # noqa: S310
                payload = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return False
        models = payload.get("models", []) if isinstance(payload, dict) else []
        return any(isinstance(item, dict) and item.get("name") == self.model for item in models)

    def generate_structured(self, prompt: str, schema: dict[str, Any]) -> str:
        if not self.model:
            raise LLMUnavailableError("No Ollama model is configured.")
        body = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "think": False,
                "format": _ollama_grammar_schema(schema),
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0},
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/chat",
            data=body,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read())
        except HTTPError as error:
            if 400 <= error.code < 500:
                raise LLMResponseError("Ollama rejected the structured-output request.") from error
            raise LLMUnavailableError("Ollama could not complete the request.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise LLMUnavailableError("Ollama could not complete the request.") from error
        except json.JSONDecodeError as error:
            raise LLMResponseError("Ollama returned an unreadable response envelope.") from error
        try:
            content = payload["message"]["content"]
            if not isinstance(content, str):
                raise TypeError
            json.loads(content)
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise LLMResponseError("Ollama returned invalid structured JSON.") from error
        return content
