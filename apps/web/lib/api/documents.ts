import { apiGet, apiUpload, hasString, isArrayOf, isRecord } from "./client";
import type { DocumentPage, SourceDocument } from "@/lib/types/api";

export const MAX_UPLOAD_SIZE_MB = 15;
export const ACCEPTED_DOCUMENT_TYPES = ".pdf,.txt,.png,.jpg,.jpeg";

export function isSourceDocument(value: unknown): value is SourceDocument {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "profile_id") &&
    hasString(value, "original_filename") &&
    hasString(value, "mime_type") &&
    hasString(value, "status") &&
    typeof value.page_count === "number" &&
    typeof value.has_extracted_text === "boolean" &&
    hasString(value, "vector_index_status") &&
    (value.vector_indexed_at === null || typeof value.vector_indexed_at === "string") &&
    typeof value.vector_chunk_count === "number" &&
    hasString(value, "created_at")
  );
}

function isDocumentPage(value: unknown): value is DocumentPage {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "document_id") &&
    typeof value.page_number === "number" &&
    typeof value.text === "string" &&
    hasString(value, "created_at")
  );
}

export function getDocuments(profileId: string, signal?: AbortSignal): Promise<SourceDocument[]> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/documents`,
    (value): value is SourceDocument[] => isArrayOf(value, isSourceDocument),
    signal,
  );
}

export function getDocument(documentId: string, signal?: AbortSignal): Promise<SourceDocument> {
  return apiGet(`/api/v1/documents/${encodeURIComponent(documentId)}`, isSourceDocument, signal);
}

export function getDocumentPages(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentPage[]> {
  return apiGet(
    `/api/v1/documents/${encodeURIComponent(documentId)}/pages`,
    (value): value is DocumentPage[] => isArrayOf(value, isDocumentPage),
    signal,
  );
}

export function uploadDocument(
  profileId: string,
  file: File,
  documentDate?: string,
  onUploadComplete?: () => void,
): Promise<SourceDocument> {
  const body = new FormData();
  body.append("file", file);
  if (documentDate) body.append("document_date", documentDate);
  return apiUpload(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/documents`,
    body,
    isSourceDocument,
    onUploadComplete,
  );
}
