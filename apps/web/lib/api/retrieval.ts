import { apiMutation, hasString, isArrayOf, isRecord } from "./client";
import type {
  DocumentIndexSummary,
  EvidenceContext,
  RetrievalSearchResponse,
} from "@/lib/types/api";

function isDocumentIndexSummary(value: unknown): value is DocumentIndexSummary {
  return isRecord(value) && hasString(value, "document_id") && value.status === "INDEXED" && typeof value.chunk_count === "number";
}

function isEvidenceContext(value: unknown): value is EvidenceContext {
  return isRecord(value) && typeof value.score === "number" && value.similarity_label === "retrieval similarity" && hasString(value, "document_id") && hasString(value, "filename") && typeof value.page_number === "number" && typeof value.text === "string" && typeof value.chunk_index === "number";
}

function isRetrievalSearchResponse(value: unknown): value is RetrievalSearchResponse {
  return isRecord(value) && hasString(value, "query") && isArrayOf(value.results, isEvidenceContext) && typeof value.indexed_document_count === "number";
}

export function indexDocument(documentId: string): Promise<DocumentIndexSummary> {
  return apiMutation(`/api/v1/documents/${encodeURIComponent(documentId)}/index`, "POST", isDocumentIndexSummary);
}

export function searchEvidence(profileId: string, query: string, topK = 5): Promise<RetrievalSearchResponse> {
  return apiMutation(`/api/v1/profiles/${encodeURIComponent(profileId)}/retrieval/search`, "POST", isRetrievalSearchResponse, { query, top_k: topK });
}
