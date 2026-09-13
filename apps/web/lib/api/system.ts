import { apiGet, hasString, isRecord } from "./client";
import type { SystemStatus } from "@/lib/types/api";

function isSystemStatus(value: unknown): value is SystemStatus {
  return (
    isRecord(value) &&
    hasString(value, "environment") &&
    hasString(value, "database") &&
    hasString(value, "upload_directory") &&
    value.vector_provider === "Pinecone" &&
    (value.vector_status === "connected" || value.vector_status === "unavailable") &&
    hasString(value, "vector_index") &&
    (value.vector_dimension === null || typeof value.vector_dimension === "number") &&
    (value.vector_metric === null || typeof value.vector_metric === "string") &&
    (value.vector_count === null || typeof value.vector_count === "number") &&
    value.embedding_provider === "Ollama" &&
    hasString(value, "embedding_model") &&
    (value.embedding_status === "connected" || value.embedding_status === "unavailable") &&
    (value.embedding_dimension === null || typeof value.embedding_dimension === "number") &&
    (value.compatibility === "compatible" || value.compatibility === "dimension_mismatch" || value.compatibility === "unavailable") &&
    value.llm_provider === "Ollama" &&
    hasString(value, "llm_model") &&
    (value.llm === "connected" || value.llm === "unavailable") &&
    value.safety_policy === "enabled" &&
    hasString(value, "safety_policy_version") &&
    (value.agent_orchestration === "enabled" || value.agent_orchestration === "unavailable")
  );
}

export function getSystemStatus(signal?: AbortSignal): Promise<SystemStatus> {
  return apiGet("/api/v1/system", isSystemStatus, signal, 15_000);
}
