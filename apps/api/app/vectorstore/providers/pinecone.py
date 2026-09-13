"""Pinecone vector store provider with profile-scoped namespaces and filters."""

from pinecone import IndexModel, Pinecone
from pinecone.exceptions import NotFoundException

from app.vectorstore.types import (
    IndexInfo,
    VectorMatch,
    VectorRecord,
    VectorStoreUnavailableError,
)


class PineconeProvider:
    def __init__(
        self,
        *,
        api_key: str,
        index_name: str,
        namespace_prefix: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.index_name = index_name
        self.namespace_prefix = namespace_prefix.strip("-") or "dr-robot"
        self.timeout_seconds = timeout_seconds

    def _client(self) -> Pinecone:
        if not self.api_key or not self.index_name:
            raise VectorStoreUnavailableError("Pinecone is not configured.")
        return Pinecone(api_key=self.api_key)

    def _describe(self, client: Pinecone) -> IndexModel:
        # The public SDK wrapper does not currently forward request timeouts for
        # describe_index, so use its generated API and preserve the public model.
        raw = client.db._index_api.describe_index(  # noqa: SLF001
            self.index_name,
            _request_timeout=self.timeout_seconds,
        )
        return IndexModel(raw)

    def _index(self):
        try:
            client = self._client()
            description = self._describe(client)
            return client.Index(host=description.host)
        except Exception as error:
            raise VectorStoreUnavailableError("Pinecone index is unavailable.") from error

    def _namespace(self, profile_id: str) -> str:
        return f"{self.namespace_prefix}-{profile_id}"

    def health_check(self) -> bool:
        try:
            return self.get_index_info().ready
        except VectorStoreUnavailableError:
            return False

    def get_index_info(self) -> IndexInfo:
        try:
            client = self._client()
            description = self._describe(client)
            state = getattr(description.status, "state", "")
            count: int | None = None
            if state == "Ready":
                stats = client.Index(host=description.host).describe_index_stats(
                    _request_timeout=self.timeout_seconds
                )
                count = int(getattr(stats, "total_vector_count", 0))
            return IndexInfo(
                name=description.name,
                dimension=int(description.dimension),
                metric=str(description.metric),
                ready=state == "Ready",
                vector_count=count,
            )
        except Exception as error:
            raise VectorStoreUnavailableError("Pinecone index is unavailable.") from error

    def upsert_chunks(self, profile_id: str, chunks: list[VectorRecord]) -> int:
        if not chunks:
            return 0
        try:
            response = self._index().upsert(
                vectors=[
                    {"id": chunk.id, "values": chunk.values, "metadata": chunk.metadata}
                    for chunk in chunks
                ],
                namespace=self._namespace(profile_id),
                show_progress=False,
                _request_timeout=self.timeout_seconds,
            )
            return int(getattr(response, "upserted_count", len(chunks)))
        except VectorStoreUnavailableError:
            raise
        except Exception as error:
            raise VectorStoreUnavailableError("Pinecone upsert failed.") from error

    def query(self, profile_id: str, vector: list[float], top_k: int) -> list[VectorMatch]:
        try:
            response = self._index().query(
                vector=vector,
                top_k=top_k,
                namespace=self._namespace(profile_id),
                filter={"profile_id": {"$eq": profile_id}},
                include_metadata=True,
                include_values=False,
                _request_timeout=self.timeout_seconds,
            )
            matches = getattr(response, "matches", []) or []
            return [
                VectorMatch(
                    id=str(match.id),
                    score=float(match.score),
                    metadata=dict(match.metadata or {}),
                )
                for match in matches
            ]
        except VectorStoreUnavailableError:
            raise
        except Exception as error:
            raise VectorStoreUnavailableError("Pinecone query failed.") from error

    def delete_document(self, document_id: str, profile_id: str) -> None:
        try:
            self._index().delete(
                namespace=self._namespace(profile_id),
                filter={
                    "$and": [
                        {"profile_id": {"$eq": profile_id}},
                        {"document_id": {"$eq": document_id}},
                    ]
                },
                _request_timeout=self.timeout_seconds,
            )
        except NotFoundException:
            return
        except VectorStoreUnavailableError:
            raise
        except Exception as error:
            raise VectorStoreUnavailableError("Pinecone document deletion failed.") from error

    def delete_profile(self, profile_id: str) -> None:
        try:
            self._index().delete(
                delete_all=True,
                namespace=self._namespace(profile_id),
                _request_timeout=self.timeout_seconds,
            )
        except NotFoundException:
            return
        except VectorStoreUnavailableError:
            raise
        except Exception as error:
            raise VectorStoreUnavailableError("Pinecone profile deletion failed.") from error
