import { apiGet, apiMutation, hasString, isArrayOf, isRecord } from "./client";
import type {
  AnalyticsEvidence,
  AnalyticsMetric,
  AvailableMetric,
  AvailableMetricsResponse,
  GlucoseContext,
  NumericSummary,
  SymptomEvidence,
  SymptomFrequencyResult,
  TrendAnalysisResult,
  WhatChangedResponse,
} from "@/lib/types/api";

function nullableNumber(value: unknown): boolean {
  return value === null || typeof value === "number";
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isPeriod(value: unknown): boolean {
  return isRecord(value) && hasString(value, "start") && hasString(value, "end") && typeof value.days === "number";
}

function isSummary(value: unknown): value is NumericSummary {
  return (
    isRecord(value) &&
    typeof value.count === "number" &&
    nullableNumber(value.mean) &&
    nullableNumber(value.median) &&
    nullableNumber(value.minimum) &&
    nullableNumber(value.maximum) &&
    nullableNumber(value.standard_deviation) &&
    nullableNumber(value.first_value) &&
    nullableNumber(value.last_value)
  );
}

function isAnalyticsEvidence(value: unknown): value is AnalyticsEvidence {
  return (
    isRecord(value) &&
    hasString(value, "observation_id") &&
    hasString(value, "recorded_at") &&
    hasString(value, "original_value") &&
    typeof value.normalized_value === "number" &&
    hasString(value, "normalized_unit") &&
    hasString(value, "provenance") &&
    hasString(value, "verification_status") &&
    hasString(value, "source_type") &&
    hasString(value, "source_label") &&
    (value.source_excerpt === null || typeof value.source_excerpt === "string") &&
    (value.view_source_path === null || typeof value.view_source_path === "string") &&
    hasString(value, "evidence_path")
  );
}

export function isTrendAnalysisResult(value: unknown): value is TrendAnalysisResult {
  return (
    isRecord(value) &&
    hasString(value, "profile_id") &&
    hasString(value, "metric") &&
    hasString(value, "metric_label") &&
    (value.context === null || typeof value.context === "string") &&
    hasString(value, "unit") &&
    hasString(value, "reference_date") &&
    isPeriod(value.recent_period) &&
    isPeriod(value.baseline_period) &&
    typeof value.recent_count === "number" &&
    typeof value.baseline_count === "number" &&
    isSummary(value.recent_summary) &&
    isSummary(value.baseline_summary) &&
    nullableNumber(value.absolute_change) &&
    nullableNumber(value.percent_change) &&
    hasString(value, "classification") &&
    hasString(value, "confidence") &&
    hasString(value, "confidence_reason") &&
    isStringArray(value.missing_data) &&
    isStringArray(value.evidence_ids) &&
    isArrayOf(value.evidence, isAnalyticsEvidence) &&
    hasString(value, "calculation_version") &&
    typeof value.stability_threshold_percent === "number" &&
    hasString(value, "explanation") &&
    hasString(value, "explanation_source") &&
    (value.display_priority === null || typeof value.display_priority === "number")
  );
}

function isAvailableMetric(value: unknown): value is AvailableMetric {
  return (
    isRecord(value) &&
    hasString(value, "metric") &&
    hasString(value, "label") &&
    isStringArray(value.contexts)
  );
}

function isAvailableMetrics(value: unknown): value is AvailableMetricsResponse {
  return (
    isRecord(value) &&
    hasString(value, "profile_id") &&
    isArrayOf(value.metrics, isAvailableMetric) &&
    isStringArray(value.symptoms)
  );
}

function isWhatChanged(value: unknown): value is WhatChangedResponse {
  return (
    isRecord(value) &&
    hasString(value, "profile_id") &&
    isArrayOf(value.results, isTrendAnalysisResult)
  );
}

function isSymptomEvidence(value: unknown): value is SymptomEvidence {
  return (
    isRecord(value) &&
    hasString(value, "symptom_id") &&
    hasString(value, "recorded_at") &&
    nullableNumber(value.severity) &&
    hasString(value, "provenance") &&
    hasString(value, "verification_status") &&
    hasString(value, "evidence_path")
  );
}

function isSymptomFrequency(value: unknown): value is SymptomFrequencyResult {
  return (
    isRecord(value) &&
    hasString(value, "profile_id") &&
    hasString(value, "symptom_name") &&
    hasString(value, "reference_date") &&
    isPeriod(value.recent_period) &&
    isPeriod(value.baseline_period) &&
    typeof value.recent_count === "number" &&
    typeof value.baseline_count === "number" &&
    nullableNumber(value.recent_rate_per_day) &&
    nullableNumber(value.baseline_rate_per_day) &&
    nullableNumber(value.percent_change) &&
    hasString(value, "classification") &&
    hasString(value, "confidence") &&
    hasString(value, "confidence_reason") &&
    isStringArray(value.missing_data) &&
    isStringArray(value.evidence_ids) &&
    isArrayOf(value.evidence, isSymptomEvidence) &&
    hasString(value, "calculation_version") &&
    hasString(value, "explanation")
  );
}

export function getAvailableMetrics(profileId: string, signal?: AbortSignal): Promise<AvailableMetricsResponse> {
  return apiGet(`/api/v1/profiles/${encodeURIComponent(profileId)}/analytics/metrics`, isAvailableMetrics, signal);
}

export function getTrend(
  profileId: string,
  metric: AnalyticsMetric,
  context?: GlucoseContext | null,
  signal?: AbortSignal,
): Promise<TrendAnalysisResult> {
  const query = new URLSearchParams({ metric });
  if (context) query.set("context", context);
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/analytics/trends?${query}`,
    isTrendAnalysisResult,
    signal,
  );
}

export function getSymptomFrequency(
  profileId: string,
  symptomName: string,
  signal?: AbortSignal,
): Promise<SymptomFrequencyResult> {
  return apiGet(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/analytics/symptoms/${encodeURIComponent(symptomName)}`,
    isSymptomFrequency,
    signal,
  );
}

export function getWhatChanged(profileId: string): Promise<WhatChangedResponse> {
  return apiMutation(
    `/api/v1/profiles/${encodeURIComponent(profileId)}/analytics/what-changed`,
    "POST",
    isWhatChanged,
    {},
  );
}
