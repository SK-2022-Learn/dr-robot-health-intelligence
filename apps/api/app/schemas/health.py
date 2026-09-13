"""Schemas returned by metadata and health endpoints."""

from typing import Literal

from pydantic import BaseModel

from app import APP_VERSION


class RootMetadata(BaseModel):
    """Public metadata for the running API process."""

    name: str
    status: Literal["running"] = "running"
    environment: str


class HealthChecks(BaseModel):
    """Non-sensitive readiness of required and optional v1 subsystems."""

    api: Literal["ok"] = "ok"
    database: Literal["ok", "unavailable"]
    llm: Literal["ok", "unavailable"]
    embedding: Literal["ok", "unavailable"]
    vector_database: Literal["ok", "unavailable"]
    upload_storage: Literal["ok", "unavailable"]
    safety: Literal["ok"] = "ok"
    agent_graph: Literal["ok", "unavailable"]


class HealthResponse(BaseModel):
    """Versioned service health response."""

    status: Literal["ok", "degraded", "unavailable"] = "ok"
    service: Literal["dr-robot-api"] = "dr-robot-api"
    version: str = APP_VERSION
    checks: HealthChecks
