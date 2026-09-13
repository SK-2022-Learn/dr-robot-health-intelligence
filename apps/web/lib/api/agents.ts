import { apiMutation, hasString, isArrayOf, isRecord } from "./client";
import type { AgentSource, AskResponse, SafetyResult } from "@/lib/types/api";

function nullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isSource(value: unknown): value is AgentSource {
  return (
    isRecord(value) &&
    hasString(value, "source_type") &&
    hasString(value, "label") &&
    nullableString(value.evidence_path) &&
    nullableString(value.entity_type) &&
    nullableString(value.entity_id) &&
    nullableString(value.document_id) &&
    (value.page_number === null || typeof value.page_number === "number")
  );
}

function isSafety(value: unknown): value is SafetyResult {
  return (
    isRecord(value) &&
    hasString(value, "decision") &&
    hasString(value, "category") &&
    hasString(value, "rule_id") &&
    hasString(value, "message") &&
    hasString(value, "policy_version")
  );
}

function isAskResponse(value: unknown): value is AskResponse {
  return (
    isRecord(value) &&
    hasString(value, "request_id") &&
    hasString(value, "intent") &&
    hasString(value, "answer") &&
    nullableString(value.conversation_id) &&
    nullableString(value.pending_id) &&
    typeof value.clarification_required === "boolean" &&
    isArrayOf(value.sources, isSource) &&
    Array.isArray(value.evidence) &&
    value.evidence.every(isRecord) &&
    (value.safety === null || isSafety(value.safety)) &&
    Array.isArray(value.warnings) &&
    value.warnings.every((item) => typeof item === "string") &&
    Array.isArray(value.actions) &&
    value.actions.every((item) => typeof item === "string") &&
    (value.structured_result === null || isRecord(value.structured_result)) &&
    (value.nodes_run === null || (Array.isArray(value.nodes_run) && value.nodes_run.every((item) => typeof item === "string")))
  );
}

export function askDrRobot(
  profileId: string,
  message: string,
  conversationId?: string,
): Promise<AskResponse> {
  return apiMutation(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/ask`,
    "POST",
    isAskResponse,
    { message, conversation_id: conversationId, include_trace: true },
    160_000,
  );
}
