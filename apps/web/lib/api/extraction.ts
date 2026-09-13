import { apiGet, apiMutation, hasString, isArrayOf, isRecord } from "./client";
import type {
  CandidateReviewResult,
  CandidateStatus,
  ExtractedCandidate,
  ExtractionSummary,
} from "@/lib/types/api";

function isCandidate(value: unknown): value is ExtractedCandidate {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "document_id") &&
    hasString(value, "candidate_type") &&
    isRecord(value.structured_data) &&
    typeof value.confidence === "number" &&
    hasString(value, "status") &&
    hasString(value, "evidence_text") &&
    (value.page_number === null || typeof value.page_number === "number") &&
    hasString(value, "created_at") &&
    hasString(value, "updated_at")
  );
}

function isExtractionSummary(value: unknown): value is ExtractionSummary {
  return (
    isRecord(value) &&
    hasString(value, "document_id") &&
    value.status === "completed" &&
    typeof value.candidate_count === "number" &&
    isRecord(value.by_type) &&
    typeof value.reused_existing === "boolean"
  );
}

function isReviewResult(value: unknown): value is CandidateReviewResult {
  return isRecord(value) && isCandidate(value.candidate) &&
    (value.trusted_record === null || isRecord(value.trusted_record));
}

export function extractDocument(documentId: string): Promise<ExtractionSummary> {
  return apiMutation(
    `/api/v1/documents/${encodeURIComponent(documentId)}/extract`,
    "POST",
    isExtractionSummary,
  );
}

export function getCandidates(
  documentId: string,
  status?: CandidateStatus,
): Promise<ExtractedCandidate[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiGet(
    `/api/v1/documents/${encodeURIComponent(documentId)}/candidates${query}`,
    (value): value is ExtractedCandidate[] => isArrayOf(value, isCandidate),
  );
}

export function acceptCandidate(candidateId: string): Promise<CandidateReviewResult> {
  return apiMutation(
    `/api/v1/candidates/${encodeURIComponent(candidateId)}/accept`,
    "POST",
    isReviewResult,
  );
}

export function correctCandidate(
  candidateId: string,
  structuredData: Record<string, unknown>,
): Promise<CandidateReviewResult> {
  return apiMutation(
    `/api/v1/candidates/${encodeURIComponent(candidateId)}/correct`,
    "PATCH",
    isReviewResult,
    { structured_data: structuredData },
  );
}

export function rejectCandidate(candidateId: string): Promise<CandidateReviewResult> {
  return apiMutation(
    `/api/v1/candidates/${encodeURIComponent(candidateId)}/reject`,
    "POST",
    isReviewResult,
  );
}
