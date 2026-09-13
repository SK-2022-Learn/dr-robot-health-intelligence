import { apiGet, hasString, isArrayOf, isRecord } from "./client";
import type {
  EvidenceResponse,
  MissingEvidenceGap,
  MissingEvidenceResponse,
  TimelineEntityType,
  TimelineItem,
  TimelineResponse,
  TimelineType,
} from "@/lib/types/api";

function nullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isTimelineItem(value: unknown): value is TimelineItem {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "entity_id") &&
    hasString(value, "entity_type") &&
    hasString(value, "timeline_type") &&
    hasString(value, "title") &&
    nullableString(value.description) &&
    nullableString(value.occurred_at) &&
    hasString(value, "provenance") &&
    hasString(value, "verification_status") &&
    hasString(value, "source_type") &&
    typeof value.has_evidence === "boolean" &&
    typeof value.has_correction === "boolean" &&
    hasString(value, "created_at")
  );
}

function isTimelineResponse(value: unknown): value is TimelineResponse {
  return (
    isRecord(value) &&
    hasString(value, "profile_id") &&
    isArrayOf(value.items, isTimelineItem) &&
    typeof value.total === "number" &&
    typeof value.limit === "number" &&
    typeof value.offset === "number"
  );
}

function isCorrection(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasString(value, "action") &&
    nullableString(value.original_value) &&
    nullableString(value.corrected_value) &&
    Array.isArray(value.changed_fields) &&
    value.changed_fields.every((field) => typeof field === "string") &&
    hasString(value, "corrected_at") &&
    nullableString(value.actor)
  );
}

function isEvidenceResponse(value: unknown): value is EvidenceResponse {
  return (
    isRecord(value) &&
    hasString(value, "profile_id") &&
    hasString(value, "entity_id") &&
    hasString(value, "entity_type") &&
    hasString(value, "source_type") &&
    hasString(value, "provenance") &&
    hasString(value, "verification_status") &&
    isRecord(value.source) &&
    hasString(value.source, "type") &&
    nullableString(value.saved_value) &&
    Array.isArray(value.correction_history) &&
    value.correction_history.every(isCorrection)
  );
}

function isGap(value: unknown): value is MissingEvidenceGap {
  return (
    isRecord(value) &&
    hasString(value, "type") &&
    hasString(value, "entity_type") &&
    hasString(value, "entity_id") &&
    hasString(value, "message")
  );
}

function isMissingEvidenceResponse(value: unknown): value is MissingEvidenceResponse {
  return (
    isRecord(value) &&
    hasString(value, "profile_id") &&
    isArrayOf(value.gaps, isGap)
  );
}

export function getTimeline(
  profileId: string,
  timelineType: TimelineType | null = null,
  sort: "asc" | "desc" = "desc",
  signal?: AbortSignal,
): Promise<TimelineResponse> {
  const query = new URLSearchParams({ sort });
  if (timelineType) query.set("type", timelineType);
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/timeline?${query}`,
    isTimelineResponse,
    signal,
  );
}

export function getTimelineEvidence(
  profileId: string,
  entityType: TimelineEntityType,
  entityId: string,
  signal?: AbortSignal,
): Promise<EvidenceResponse> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/evidence/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
    isEvidenceResponse,
    signal,
  );
}

export function getMissingEvidence(
  profileId: string,
  signal?: AbortSignal,
): Promise<MissingEvidenceResponse> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/evidence/gaps`,
    isMissingEvidenceResponse,
    signal,
  );
}
