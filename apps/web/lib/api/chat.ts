import { apiGet, apiMutation, hasString, isArrayOf, isRecord } from "./client";
import type {
  ChatMessage,
  ChatMessageResponse,
  ClarificationQuestion,
  ConfirmationResponse,
  ConversationDetail,
  ConversationSummary,
  DailyHealthExtraction,
  DailyObservation,
  PendingHealthEntry,
  SafetyResult,
  TrustedRecord,
} from "@/lib/types/api";

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isClarification(value: unknown): value is ClarificationQuestion {
  return (
    isRecord(value) &&
    hasString(value, "field") &&
    hasString(value, "question") &&
    Array.isArray(value.options) &&
    value.options.every((item) => typeof item === "string")
  );
}

function isDailyObservation(value: unknown): value is DailyObservation {
  if (!isRecord(value) || !hasString(value, "entry_type")) return false;
  if (value.entry_type === "glucose") {
    return (
      typeof value.value === "number" &&
      hasString(value, "unit") &&
      hasString(value, "context") &&
      typeof value.confidence === "number"
    );
  }
  if (value.entry_type === "blood_pressure") {
    return (
      typeof value.systolic === "number" &&
      typeof value.diastolic === "number" &&
      value.unit === "mmHg" &&
      typeof value.confidence === "number"
    );
  }
  if (value.entry_type === "weight") {
    return (
      typeof value.value === "number" &&
      isNullableString(value.unit) &&
      typeof value.confidence === "number"
    );
  }
  return false;
}

export function isDailyHealthExtraction(value: unknown): value is DailyHealthExtraction {
  return (
    isRecord(value) &&
    isArrayOf(value.observations, isDailyObservation) &&
    Array.isArray(value.symptoms) &&
    value.symptoms.every(
      (item) =>
        isRecord(item) &&
        hasString(item, "name") &&
        hasString(item, "severity") &&
        typeof item.confidence === "number",
    ) &&
    Array.isArray(value.activities) &&
    value.activities.every(
      (item) =>
        isRecord(item) &&
        hasString(item, "activity_type") &&
        typeof item.confidence === "number",
    ) &&
    Array.isArray(value.sleep_entries) &&
    value.sleep_entries.every(
      (item) =>
        isRecord(item) &&
        typeof item.duration_minutes === "number" &&
        typeof item.confidence === "number",
    ) &&
    isArrayOf(value.clarifications, isClarification) &&
    Array.isArray(value.warnings) &&
    value.warnings.every((item) => typeof item === "string")
  );
}

function isTrustedRecord(value: unknown): value is TrustedRecord {
  return (
    isRecord(value) &&
    (value.record_type === "observations" || value.record_type === "symptoms") &&
    hasString(value, "record_id")
  );
}

function isPending(value: unknown): value is PendingHealthEntry {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "conversation_id") &&
    hasString(value, "message_id") &&
    hasString(value, "profile_id") &&
    hasString(value, "status") &&
    typeof value.was_corrected === "boolean" &&
    isDailyHealthExtraction(value.extraction) &&
    isArrayOf(value.trusted_records, isTrustedRecord) &&
    hasString(value, "created_at") &&
    hasString(value, "updated_at")
  );
}

function isMessage(value: unknown): value is ChatMessage {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "conversation_id") &&
    hasString(value, "role") &&
    hasString(value, "content") &&
    hasString(value, "created_at")
  );
}

function isConversationSummary(value: unknown): value is ConversationSummary {
  return (
    isRecord(value) &&
    hasString(value, "id") &&
    hasString(value, "profile_id") &&
    isNullableString(value.title) &&
    hasString(value, "created_at") &&
    hasString(value, "updated_at")
  );
}

function isConversationDetail(value: unknown): value is ConversationDetail {
  if (!isConversationSummary(value)) return false;
  const detail = value as unknown as Record<string, unknown>;
  return isArrayOf(detail.messages, isMessage) && isArrayOf(detail.pending_entries, isPending);
}

function isSafetyResult(value: unknown): value is SafetyResult {
  return (
    isRecord(value) &&
    hasString(value, "decision") &&
    hasString(value, "category") &&
    hasString(value, "rule_id") &&
    hasString(value, "message") &&
    isNullableString(value.safe_response_override) &&
    typeof value.requires_professional_evaluation === "boolean" &&
    typeof value.emergency_guidance === "boolean" &&
    isRecord(value.audit_metadata) &&
    hasString(value, "policy_version")
  );
}

function isMessageResponse(value: unknown): value is ChatMessageResponse {
  return (
    isRecord(value) &&
    hasString(value, "message_id") &&
    isNullableString(value.pending_id) &&
    hasString(value, "status") &&
    (value.extraction === null || isDailyHealthExtraction(value.extraction)) &&
    isArrayOf(value.questions, isClarification) &&
    hasString(value, "assistant_message") &&
    (value.safety === undefined || value.safety === null || isSafetyResult(value.safety))
  );
}

function isConfirmation(value: unknown): value is ConfirmationResponse {
  return (
    isRecord(value) &&
    isPending(value.pending) &&
    isArrayOf(value.trusted_records, isTrustedRecord) &&
    typeof value.already_confirmed === "boolean"
  );
}

const inFlightConversations = new Map<string, Promise<ConversationSummary>>();

export function createConversation(profileId: string): Promise<ConversationSummary> {
  const existing = inFlightConversations.get(profileId);
  if (existing) return existing;
  const request = apiMutation(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/conversations`,
    "POST",
    isConversationSummary,
    {},
  );
  const trackedRequest = request.finally(() => {
    if (inFlightConversations.get(profileId) === trackedRequest) {
      inFlightConversations.delete(profileId);
    }
  });
  inFlightConversations.set(profileId, trackedRequest);
  return trackedRequest;
}

export function getConversations(
  profileId: string,
  signal?: AbortSignal,
): Promise<ConversationSummary[]> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/conversations`,
    (value): value is ConversationSummary[] => isArrayOf(value, isConversationSummary),
    signal,
  );
}

export function getConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ConversationDetail> {
  return apiGet(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}`,
    isConversationDetail,
    signal,
  );
}

export function postChatMessage(
  conversationId: string,
  content: string,
): Promise<ChatMessageResponse> {
  return apiMutation(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
    "POST",
    isMessageResponse,
    { content },
  );
}

export function clarifyPending(
  pendingId: string,
  answers: Record<string, string>,
): Promise<ChatMessageResponse> {
  return apiMutation(
    `/api/v1/chat/pending/${encodeURIComponent(pendingId)}/clarify`,
    "POST",
    isMessageResponse,
    { answers },
  );
}

export function correctPending(
  pendingId: string,
  extraction: DailyHealthExtraction,
): Promise<PendingHealthEntry> {
  return apiMutation(
    `/api/v1/chat/pending/${encodeURIComponent(pendingId)}`,
    "PATCH",
    isPending,
    { extraction },
  );
}

export function confirmPending(pendingId: string): Promise<ConfirmationResponse> {
  return apiMutation(
    `/api/v1/chat/pending/${encodeURIComponent(pendingId)}/confirm`,
    "POST",
    isConfirmation,
  );
}

export function rejectPending(pendingId: string): Promise<PendingHealthEntry> {
  return apiMutation(
    `/api/v1/chat/pending/${encodeURIComponent(pendingId)}/reject`,
    "POST",
    isPending,
  );
}
