"""Local Ollama embedding provider."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.embeddings.types import EmbeddingResponseError, EmbeddingUnavailableError


class OllamaEmbeddingProvider:
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

    def embed_text(self, text: str) -> list[float]:
        results = self.embed_batch([text])
        if len(results) != 1:
            raise EmbeddingResponseError("Ollama returned an unexpected embedding count.")
        return results[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.model:
            raise EmbeddingUnavailableError("No Ollama embedding model is configured.")
        body = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/embed",
            data=body,
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise EmbeddingUnavailableError("Ollama embeddings are unavailable.") from error
        except json.JSONDecodeError as error:
            raise EmbeddingResponseError(
                "Ollama returned an unreadable embedding response."
            ) from error
        embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise EmbeddingResponseError("Ollama returned an unexpected embedding response.")
        validated: list[list[float]] = []
        for embedding in embeddings:
            if not isinstance(embedding, list) or not embedding:
                raise EmbeddingResponseError("Ollama returned an empty embedding.")
            if not all(isinstance(value, int | float) for value in embedding):
                raise EmbeddingResponseError("Ollama returned a non-numeric embedding.")
            validated.append([float(value) for value in embedding])
        return validated
