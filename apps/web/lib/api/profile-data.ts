import { apiGet, hasString, isArrayOf, isRecord } from "./client";
import { getDocuments } from "./documents";
import { getProfileEvents } from "./events";
import type {
  Medication,
  Observation,
  ProfileSnapshot,
  Symptom,
} from "@/lib/types/api";

function isObservation(value: unknown): value is Observation {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "profile_id") &&
    hasString(value, "display_name") &&
    hasString(value, "observed_at") &&
    hasString(value, "provenance") &&
    hasString(value, "verification_status")
  );
}

function isMedication(value: unknown): value is Medication {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "profile_id") &&
    hasString(value, "name") &&
    typeof value.is_active === "boolean" &&
    hasString(value, "provenance") &&
    hasString(value, "verification_status")
  );
}

function isSymptom(value: unknown): value is Symptom {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "profile_id") &&
    hasString(value, "name") &&
    hasString(value, "provenance") &&
    hasString(value, "verification_status")
  );
}

export function getObservations(profileId: string, signal?: AbortSignal): Promise<Observation[]> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/observations`,
    (value): value is Observation[] => isArrayOf(value, isObservation),
    signal,
  );
}

export function getMedications(profileId: string, signal?: AbortSignal): Promise<Medication[]> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/medications`,
    (value): value is Medication[] => isArrayOf(value, isMedication),
    signal,
  );
}

export function getSymptoms(profileId: string, signal?: AbortSignal): Promise<Symptom[]> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/symptoms`,
    (value): value is Symptom[] => isArrayOf(value, isSymptom),
    signal,
  );
}

export async function getProfileSnapshot(
  profileId: string,
  signal?: AbortSignal,
): Promise<ProfileSnapshot> {
  const [events, observations, medications, symptoms, documents] = await Promise.all([
    getProfileEvents(profileId, signal),
    getObservations(profileId, signal),
    getMedications(profileId, signal),
    getSymptoms(profileId, signal),
    getDocuments(profileId, signal),
  ]);
  return { events, observations, medications, symptoms, documents };
}
