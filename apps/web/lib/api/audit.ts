import { apiGet, hasString, isArrayOf, isRecord } from "./client";
import type { AuditLog } from "@/lib/types/api";

function isAuditLog(value: unknown): value is AuditLog {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "action") &&
    hasString(value, "entity_type") &&
    hasString(value, "entity_id") &&
    hasString(value, "created_at")
  );
}

export function getAuditLogs(signal?: AbortSignal): Promise<AuditLog[]> {
  return apiGet("/api/v1/audit", (value): value is AuditLog[] => isArrayOf(value, isAuditLog), signal);
}

