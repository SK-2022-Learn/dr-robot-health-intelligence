"use client";

import { useCallback, useMemo, useState } from "react";

import { AnalyticsWhyPanel } from "@/components/analytics/analytics-why-panel";
import { TrendChart } from "@/components/analytics/trend-chart";
import { useProfile } from "@/components/health/profile-context";
import { Card, EmptyState, ErrorState, LoadingState, PageHeading, StatusPill } from "@/components/ui";
import {
  getAvailableMetrics,
  getSymptomFrequency,
  getTrend,
  getWhatChanged,
} from "@/lib/api/analytics";
import { useResource } from "@/lib/hooks/use-resource";
import type {
  AnalyticsMetric,
  GlucoseContext,
  SymptomFrequencyResult,
  TrendAnalysisResult,
} from "@/lib/types/api";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

type AnalyticsResult = TrendAnalysisResult | SymptomFrequencyResult;
type SelectorOption = { key: string; label: string };

function isNumeric(result: AnalyticsResult): result is TrendAnalysisResult {
  return "metric" in result;
}

function trendTitle(result: TrendAnalysisResult): string {
  return result.context
    ? `${friendlyLabel(result.context)} ${result.metric_label.toLowerCase()}`
    : result.metric_label;
}

function formatValue(
  value: number | null,
  result: TrendAnalysisResult,
  signed = false,
): string {
  if (value === null) return "Unavailable";
  const sign = signed && value > 0 ? "+" : value < 0 ? "−" : "";
  if (result.metric === "sleep_duration") {
    const rounded = Math.round(Math.abs(value));
    return `${sign}${Math.floor(rounded / 60)}h ${rounded % 60}m`;
  }
  return `${sign}${Math.abs(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${result.unit}`;
}

function tone(classification: TrendAnalysisResult["classification"]): "neutral" | "good" | "warm" {
  if (classification === "STABLE") return "good";
  if (classification === "INSUFFICIENT_DATA") return "warm";
  return "neutral";
}

export default function InsightsPage() {
  const { activeProfile, loading, error } = useProfile();
  const [chosenKey, setChosenKey] = useState<string | null>(null);
  const [why, setWhy] = useState<AnalyticsResult | null>(null);
  const metricsLoader = useCallback(
    (signal?: AbortSignal) => getAvailableMetrics(activeProfile!.id, signal),
    [activeProfile],
  );
  const changedLoader = useCallback(() => getWhatChanged(activeProfile!.id), [activeProfile]);
  const metrics = useResource(metricsLoader, activeProfile?.id ?? null);
  const changed = useResource(changedLoader, activeProfile?.id ?? null);
  const options = useMemo<SelectorOption[]>(() => {
    const result: SelectorOption[] = [];
    for (const item of metrics.data?.metrics ?? []) {
      if (item.metric === "glucose" && item.contexts.length) {
        result.push(...item.contexts.map((context) => ({
          key: `metric|${item.metric}|${context}`,
          label: `${friendlyLabel(context)} glucose`,
        })));
      } else {
        result.push({ key: `metric|${item.metric}|`, label: item.label });
      }
    }
    result.push(...(metrics.data?.symptoms ?? []).map((name) => ({
      key: `symptom|${name}`,
      label: `${name} frequency`,
    })));
    return result;
  }, [metrics.data]);
  const selectedKey = chosenKey ?? options[0]?.key ?? null;
  const detailLoader = useCallback(
    (signal?: AbortSignal) => {
      if (!activeProfile || !selectedKey) throw new Error("No analytics metric is selected.");
      const [kind, value, context] = selectedKey.split("|");
      return kind === "symptom"
        ? getSymptomFrequency(activeProfile.id, value, signal)
        : getTrend(
            activeProfile.id,
            value as AnalyticsMetric,
            (context || null) as GlucoseContext | null,
            signal,
          );
    },
    [activeProfile, selectedKey],
  );
  const detail = useResource<AnalyticsResult>(
    detailLoader,
    activeProfile && selectedKey ? `${activeProfile.id}:${selectedKey}` : null,
  );

  if (loading) return <LoadingState label="Loading profile..." />;
  if (error) return <ErrorState message={error} />;
  if (!activeProfile) {
    return <EmptyState title="No profile selected" message="Choose a profile to compare recorded history." />;
  }

  return (
    <>
      <PageHeading
        eyebrow="Deterministic record analysis"
        title="Insights"
        description="See what changed against your personal baseline—without diagnosis, forecasting, or population norms."
      />
      <p className="personal-baseline-label">Compared with your own recorded history</p>

      <div className="analytics-layout">
        <main className="analytics-main">
          <Card title="What Changed?">
            <p className="helper-text">
              Display priority uses data sufficiency, relative magnitude, recency, and data confidence—not clinical importance.
            </p>
            {changed.loading ? <LoadingState label="Calculating recorded changes..." /> : changed.error ? (
              <ErrorState message={changed.error} />
            ) : !changed.data?.results.length ? (
              <EmptyState title="No supported metrics yet" message="Add verified readings to begin a personal-baseline comparison." />
            ) : (
              <div className="change-grid">
                {changed.data.results.map((result) => (
                  <article className="trend-card" key={`${result.metric}-${result.context ?? "all"}`}>
                    <div className="trend-card-head">
                      <div><span>Priority {result.display_priority}</span><h3>{trendTitle(result)}</h3></div>
                      <StatusPill tone={tone(result.classification)}>{friendlyLabel(result.classification)}</StatusPill>
                    </div>
                    <div className="trend-comparison">
                      <div><span>Recent average</span><strong>{formatValue(result.recent_summary.mean, result)}</strong></div>
                      <div><span>Baseline average</span><strong>{formatValue(result.baseline_summary.mean, result)}</strong></div>
                      <div><span>Change</span><strong>{formatValue(result.absolute_change, result, true)}</strong></div>
                    </div>
                    <div className="trend-card-foot">
                      <span>Data confidence: {friendlyLabel(result.confidence)}</span>
                      <button onClick={() => setWhy(result)}>WHY?</button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Card>

          <Card title="Personal Baselines">
            <div className="analytics-toolbar">
              <label htmlFor="metric-selector">Metric</label>
              <select
                id="metric-selector"
                value={selectedKey ?? ""}
                onChange={(event) => { setChosenKey(event.target.value); setWhy(null); }}
                disabled={!options.length}
              >
                {!options.length && <option value="">No supported data</option>}
                {options.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
              </select>
            </div>
            {metrics.loading || detail.loading ? <LoadingState label="Calculating personal baseline..." /> : metrics.error ? (
              <ErrorState message={metrics.error} />
            ) : detail.error ? <ErrorState message={detail.error} /> : !detail.data ? (
              <EmptyState title="Not enough stored information" message="No supported metric is available for this profile." />
            ) : isNumeric(detail.data) ? (
              <NumericDetail result={detail.data} onWhy={() => setWhy(detail.data)} />
            ) : <SymptomDetail result={detail.data} onWhy={() => setWhy(detail.data)} />}
          </Card>
        </main>

        {why && <AnalyticsWhyPanel result={why} onClose={() => setWhy(null)} />}
      </div>
    </>
  );
}

function NumericDetail({ result, onWhy }: { result: TrendAnalysisResult; onWhy: () => void }) {
  const insufficient = result.classification === "INSUFFICIENT_DATA";
  return (
    <div className="baseline-detail">
      <div className="baseline-title">
        <div><span className="eyebrow">{trendTitle(result)}</span><h3>{friendlyLabel(result.classification)}</h3></div>
        <StatusPill tone={tone(result.classification)}>Data confidence: {friendlyLabel(result.confidence)}</StatusPill>
      </div>
      {insufficient && (
        <div className="insufficient-banner">
          <strong>Not enough data to compare.</strong>
          <span>Recent readings: {result.recent_count}</span>
          <span>Baseline readings: {result.baseline_count}</span>
          {result.missing_data.map((message) => <p key={message}>{message}</p>)}
        </div>
      )}
      <div className="period-strip">
        <span>Recent: {formatDate(`${result.recent_period.start}T00:00:00`)} – {formatDate(`${result.recent_period.end}T00:00:00`)}</span>
        <span>Baseline: {formatDate(`${result.baseline_period.start}T00:00:00`)} – {formatDate(`${result.baseline_period.end}T00:00:00`)}</span>
      </div>
      <div className="trend-comparison large">
        <div><span>Recent</span><strong>{formatValue(result.recent_summary.mean, result)}</strong></div>
        <div><span>Baseline</span><strong>{formatValue(result.baseline_summary.mean, result)}</strong></div>
        <div><span>Change</span><strong>{formatValue(result.absolute_change, result, true)}</strong></div>
      </div>
      <p className="analytics-explanation">{result.explanation}</p>
      <TrendChart result={result} />
      <div className="analytics-actions"><button onClick={onWhy}>WHY?</button></div>
    </div>
  );
}

function SymptomDetail({ result, onWhy }: { result: SymptomFrequencyResult; onWhy: () => void }) {
  return (
    <div className="baseline-detail">
      <div className="baseline-title">
        <div><span className="eyebrow">Symptom frequency</span><h3>{result.symptom_name}: {friendlyLabel(result.classification)}</h3></div>
        <StatusPill tone={tone(result.classification)}>Data confidence: {friendlyLabel(result.confidence)}</StatusPill>
      </div>
      {result.classification === "INSUFFICIENT_DATA" && (
        <div className="insufficient-banner"><strong>Not enough data to compare.</strong>{result.missing_data.map((message) => <p key={message}>{message}</p>)}</div>
      )}
      <div className="trend-comparison large">
        <div><span>Recent reports</span><strong>{result.recent_count}</strong></div>
        <div><span>Baseline reports</span><strong>{result.baseline_count}</strong></div>
        <div><span>Rate change</span><strong>{result.percent_change === null ? "Unavailable" : `${result.percent_change}%`}</strong></div>
      </div>
      <p className="analytics-explanation">{result.explanation}</p>
      <p className="helper-text">No record does not mean no symptom. Unlogged days remain unknown.</p>
      <div className="analytics-actions"><button onClick={onWhy}>WHY?</button></div>
    </div>
  );
}
