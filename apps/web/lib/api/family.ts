import { apiGet, apiMutation, hasString, isArrayOf, isRecord } from "./client";
import type {
  AccessLevel,
  FamilyConditionContributor,
  FamilyConditionPattern,
  FamilyData,
  FamilyPermission,
  FamilyProfileSummary,
  FamilyRelationship,
  FamilyPatternsResponse,
} from "@/lib/types/api";

const accessLevels = new Set(["PRIVATE", "CAREGIVER", "FAMILY_SUMMARY", "FULL"]);

function isProfile(value: unknown): value is FamilyProfileSummary {
  return isRecord(value) && hasString(value, "profile_id") && hasString(value, "label") &&
    hasString(value, "relationship_to_owner") && hasString(value, "access_level") &&
    accessLevels.has(value.access_level as string) && typeof value.is_private === "boolean" &&
    (value.permission_id === null || typeof value.permission_id === "string") &&
    (value.documented_condition_count === null || typeof value.documented_condition_count === "number") &&
    (value.shared_conditions === null || isArrayOf(value.shared_conditions, (row): row is string => typeof row === "string"));
}

function isRelationship(value: unknown): value is FamilyRelationship {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "source_profile_id") &&
    hasString(value, "target_profile_id") &&
    hasString(value, "relationship_type") &&
    hasString(value, "created_at")
  );
}

function isFamilyData(value: unknown): value is FamilyData {
  return (
    isRecord(value) &&
    hasString(value, "requester_user_id") &&
    hasString(value, "selected_profile_id") &&
    isArrayOf(value.profiles, isProfile) &&
    isArrayOf(value.relationships, isRelationship)
  );
}

function isContributor(value: unknown): value is FamilyConditionContributor {
  return isRecord(value) && hasString(value, "profile_id") && hasString(value, "label") &&
    hasString(value, "access_level") && hasString(value, "state") &&
    typeof value.generation === "number" && hasString(value, "branch") &&
    Array.isArray(value.evidence);
}

function isPattern(value: unknown): value is FamilyConditionPattern {
  return isRecord(value) && hasString(value, "condition_name") &&
    typeof value.profile_count === "number" && typeof value.permitted_profile_count === "number" &&
    typeof value.generation_count === "number" && Array.isArray(value.branches) &&
    isArrayOf(value.contributing_profiles, isContributor) &&
    isArrayOf(value.profile_states, isContributor) && typeof value.evidence_count === "number" &&
    hasString(value, "confidence") && hasString(value, "statement") && Array.isArray(value.notes);
}

function isPatterns(value: unknown): value is FamilyPatternsResponse {
  return isRecord(value) && hasString(value, "requester_user_id") &&
    hasString(value, "selected_profile_id") && isArrayOf(value.patterns, isPattern);
}

function isPermission(value: unknown): value is FamilyPermission {
  return isRecord(value) && hasString(value, "permission_id") &&
    hasString(value, "profile_id") && hasString(value, "access_level") &&
    (value.scope === null || typeof value.scope === "string");
}

function query(profileId: string, requesterUserId: string): string {
  return new URLSearchParams({
    selected_profile_id: profileId,
    requester_user_id: requesterUserId,
  }).toString();
}

export function getFamily(profileId: string, requesterUserId: string, signal?: AbortSignal): Promise<FamilyData> {
  return apiGet(`/api/v1/family?${query(profileId, requesterUserId)}`, isFamilyData, signal);
}

export function getFamilyPatterns(profileId: string, requesterUserId: string, signal?: AbortSignal): Promise<FamilyPatternsResponse> {
  return apiGet(`/api/v1/family/patterns?${query(profileId, requesterUserId)}`, isPatterns, signal);
}

export function updateFamilyPermission(permissionId: string, requesterUserId: string, accessLevel: AccessLevel): Promise<FamilyPermission> {
  return apiMutation(
    `/api/v1/family/permissions/${encodeURIComponent(permissionId)}`,
    "PATCH",
    isPermission,
    { requester_user_id: requesterUserId, access_level: accessLevel },
  );
}
