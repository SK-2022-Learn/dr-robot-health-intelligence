import { apiGet, hasString, isArrayOf, isRecord } from "./client";
import type { Profile } from "@/lib/types/api";

export function isProfile(value: unknown): value is Profile {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "owner_user_id") &&
    hasString(value, "display_name") &&
    hasString(value, "relationship_to_owner") &&
    hasString(value, "access_level") &&
    typeof value.is_active === "boolean"
  );
}

export function getProfiles(signal?: AbortSignal): Promise<Profile[]> {
  return apiGet("/api/v1/profiles", (value): value is Profile[] => isArrayOf(value, isProfile), signal);
}

