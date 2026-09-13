import { isTrendAnalysisResult } from "./analytics";
import { apiMutation, hasString, isArrayOf, isRecord } from "./client";

import type { DoctorVisitBrief, VisitEvidenceReference } from "@/lib/types/api";

function nullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isEvidence(value: unknown): value is VisitEvidenceReference {
  return (
    isRecord(value) &&
    hasString(value, "entity_type") &&
    hasString(value, "entity_id") &&
    hasString(value, "source_type") &&
    hasString(value, "source_label") &&
    hasString(value, "provenance") &&
    hasString(value, "verification_status") &&
    typeof value.has_evidence === "boolean" &&
    hasString(value, "evidence_path")
  );
}

function isHistory(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    hasString(value, "record_id") &&
    hasString(value, "title") &&
    hasString(value, "timeline_type") &&
    nullableString(value.documented_date) &&
    nullableString(value.end_date) &&
    isEvidence(value.evidence)
  );
}

function isMedication(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    hasString(value, "record_id") &&
    hasString(value, "name") &&
    nullableString(value.dose) &&
    nullableString(value.dose_unit) &&
    nullableString(value.frequency) &&
    nullableString(value.route) &&
    nullableString(value.start_date) &&
    nullableString(value.end_date) &&
    hasString(value, "last_updated_at") &&
    typeof value.reconciliation_needed === "boolean" &&
    isEvidence(value.evidence)
  );
}

function isObservation(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    hasString(value, "record_id") &&
    hasString(value, "name") &&
    hasString(value, "value") &&
    nullableString(value.unit) &&
    hasString(value, "observed_at") &&
    nullableString(value.interpretation) &&
    isEvidence(value.evidence)
  );
}

function isSymptom(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    hasString(value, "name") &&
    typeof value.report_count === "number" &&
    hasString(value, "most_recent") &&
    hasString(value, "statement") &&
    isArrayOf(value.evidence, isEvidence)
  );
}

function isRecentChange(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    hasString(value, "key") &&
    hasString(value, "statement") &&
    isTrendAnalysisResult(value.analysis)
  );
}

function isMissingEvidence(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    hasString(value, "type") &&
    hasString(value, "message") &&
    nullableString(value.entity_type) &&
    nullableString(value.entity_id)
  );
}

function isQuestion(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    hasString(value, "question_id") &&
    hasString(value, "trigger") &&
    hasString(value, "question")
  );
}

function isEvidenceSummary(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    hasString(value, "key") &&
    hasString(value, "label") &&
    typeof value.count === "number"
  );
}

function isBrief(value: unknown): value is DoctorVisitBrief {
  return (
    isRecord(value) &&
    hasString(value, "profile_id") &&
    hasString(value, "profile_display_name") &&
    (value.profile_age === null || typeof value.profile_age === "number") &&
    nullableString(value.date_of_birth) &&
    hasString(value, "relationship_to_owner") &&
    hasString(value, "generated_at") &&
    hasString(value, "data_cutoff") &&
    hasString(value, "summary_version") &&
    hasString(value, "overview") &&
    hasString(value, "overview_source") &&
    hasString(value, "rewrite_status") &&
    isArrayOf(value.known_history, isHistory) &&
    isArrayOf(value.medications, isMedication) &&
    isArrayOf(value.recent_labs, isObservation) &&
    isArrayOf(value.recent_measurements, isObservation) &&
    isArrayOf(value.recent_symptoms, isSymptom) &&
    isArrayOf(value.recent_changes, isRecentChange) &&
    isArrayOf(value.missing_evidence, isMissingEvidence) &&
    isArrayOf(value.questions_to_discuss, isQuestion) &&
    isArrayOf(value.evidence_summary, isEvidenceSummary) &&
    isStringArray(value.safety_notes)
  );
}

const inFlightBriefs = new Map<string, Promise<DoctorVisitBrief>>();

export function generateDoctorVisitBrief(profileId: string): Promise<DoctorVisitBrief> {
  const existing = inFlightBriefs.get(profileId);
  if (existing) return existing;

  const request = apiMutation(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/doctor-visit/generate`,
    "POST",
    isBrief,
  );
  const trackedRequest = request.finally(() => {
    if (inFlightBriefs.get(profileId) === trackedRequest) {
      inFlightBriefs.delete(profileId);
    }
  });
  inFlightBriefs.set(profileId, trackedRequest);
  return trackedRequest;
}
