import { apiGet, hasString, isArrayOf, isRecord } from "./client";
import type { HealthEvent } from "@/lib/types/api";

export function isHealthEvent(value: unknown): value is HealthEvent {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "profile_id") &&
    hasString(value, "event_type") &&
    hasString(value, "event_date") &&
    hasString(value, "title") &&
    hasString(value, "verification_status") &&
    hasString(value, "provenance")
  );
}

export function getProfileEvents(profileId: string, signal?: AbortSignal): Promise<HealthEvent[]> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/events`,
    (value): value is HealthEvent[] => isArrayOf(value, isHealthEvent),
    signal,
  );
}

