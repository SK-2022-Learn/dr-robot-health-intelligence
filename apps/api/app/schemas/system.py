"""Non-sensitive system configuration and availability contract."""

from typing import Literal

from app.schemas.common import SchemaModel


class SystemStatusRead(SchemaModel):
    environment: str
    database: Literal["connected", "unavailable"]
    upload_directory: Literal["configured", "unavailable"]
    vector_provider: Literal["Pinecone"] = "Pinecone"
    vector_status: Literal["connected", "unavailable"]
    vector_index: str
    vector_dimension: int | None
    vector_metric: str | None
    vector_count: int | None
    embedding_provider: Literal["Ollama"] = "Ollama"
    embedding_model: str
    embedding_status: Literal["connected", "unavailable"]
    embedding_dimension: int | None
    compatibility: Literal["compatible", "dimension_mismatch", "unavailable"]
    llm_provider: Literal["Ollama"] = "Ollama"
    llm_model: str
    llm: Literal["connected", "unavailable"]
    safety_policy: Literal["enabled"] = "enabled"
    safety_policy_version: str
    agent_orchestration: Literal["enabled", "unavailable"]
