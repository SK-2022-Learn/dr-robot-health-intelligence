import { apiGet, hasString, isRecord } from "./client";
import type { HealthResponse } from "@/lib/types/api";

function isHealthResponse(value: unknown): value is HealthResponse {
  return (
    isRecord(value) &&
    hasString(value, "status") &&
    isRecord(value.checks) &&
    value.checks.api === "ok" &&
    typeof value.checks.database === "string"
  );
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiGet("/api/v1/health", isHealthResponse, signal);
}

