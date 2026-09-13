"use client";

import Link from "next/link";

import type {
  AnalyticsEvidence,
  SymptomEvidence,
  SymptomFrequencyResult,
  TrendAnalysisResult,
} from "@/lib/types/api";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

type AnalyticsResult = TrendAnalysisResult | SymptomFrequencyResult;
type EvidenceRow = AnalyticsEvidence | SymptomEvidence;

function isNumeric(result: AnalyticsResult): result is TrendAnalysisResult {
  return "metric" in result;
}

function periodLabel(start: string, end: string): string {
  return `${formatDate(`${start}T00:00:00`)} – ${formatDate(`${end}T00:00:00`)}`;
}

export function AnalyticsWhyPanel({ result, onClose }: { result: AnalyticsResult; onClose: () => void }) {
  const recentEvidence = result.evidence.filter(
    (point) => point.recorded_at.slice(0, 10) >= result.recent_period.start,
  );
  const baselineEvidence = result.evidence.filter(
    (point) => point.recorded_at.slice(0, 10) <= result.baseline_period.end,
  );
  return (
    <aside className="evidence-drawer analytics-why" aria-label="Analytics calculation evidence">
      <div className="evidence-drawer-head">
        <div>
          <p className="eyebrow">HOW IT WAS CALCULATED</p>
          <h2>{isNumeric(result) ? result.metric_label : `${result.symptom_name} frequency`}</h2>
        </div>
        <button onClick={onClose} aria-label="Close calculation evidence">Close</button>
      </div>
      <div className="evidence-detail">
        <section>
          <h3>Personal comparison periods</h3>
          <dl className="evidence-meta">
            <div><dt>Recent</dt><dd>{periodLabel(result.recent_period.start, result.recent_period.end)}</dd></div>
            <div><dt>Baseline</dt><dd>{periodLabel(result.baseline_period.start, result.baseline_period.end)}</dd></div>
          </dl>
          <small>Both boundaries are inclusive. The periods do not overlap.</small>
        </section>

        <section>
          <h3>Calculation</h3>
          {isNumeric(result) ? (
            <p>
              Recent mean {result.recent_summary.mean ?? "unavailable"} {result.unit} minus baseline mean{" "}
              {result.baseline_summary.mean ?? "unavailable"} {result.unit} ={" "}
              {result.absolute_change ?? "unavailable"} {result.unit}. Changes within ±
              {result.stability_threshold_percent}% are classified as stable.
            </p>
          ) : (
            <p>
              {result.recent_count} reports across {result.recent_period.days} recent days compared with{" "}
              {result.baseline_count} reports across {result.baseline_period.days} baseline days. Unlogged days are not zero.
            </p>
          )}
          <dl className="evidence-meta">
            <div><dt>Classification</dt><dd>{friendlyLabel(result.classification)}</dd></div>
            <div><dt>Data confidence</dt><dd>{friendlyLabel(result.confidence)}</dd></div>
            <div><dt>Version</dt><dd>{result.calculation_version}</dd></div>
          </dl>
          <p className="helper-text">{result.confidence_reason}</p>
        </section>

        <EvidenceList title="Recent values" rows={recentEvidence} numeric={isNumeric(result)} />
        <EvidenceList title="Baseline values" rows={baselineEvidence} numeric={isNumeric(result)} />

        <section>
          <h3>Missing data</h3>
          {result.missing_data.length ? (
            <ul>{result.missing_data.map((message) => <li key={message}>{message}</li>)}</ul>
          ) : <p>No excluded or missing comparison data was detected.</p>}
        </section>
      </div>
    </aside>
  );
}

function EvidenceList({
  title,
  rows,
  numeric,
}: {
  title: string;
  rows: EvidenceRow[];
  numeric: boolean;
}) {
  return (
    <section>
      <h3>{title}</h3>
      {rows.length === 0 ? <p className="helper-text">No recorded values in this period.</p> : (
        <div className="analytics-evidence-list">
          {rows.map((point) => {
            const numericPoint = numeric && "normalized_value" in point ? point : null;
            return (
              <div key={"observation_id" in point ? point.observation_id : point.symptom_id}>
                <div>
                  <strong>
                    {numericPoint
                      ? `${numericPoint.normalized_value} ${numericPoint.normalized_unit}`
                      : `Reported${"severity" in point && point.severity !== null ? ` · severity ${point.severity}/10` : ""}`}
                  </strong>
                  <time>{formatDate(point.recorded_at)}</time>
                </div>
                {numericPoint && (
                  <>
                    <span>{numericPoint.source_label} · {friendlyLabel(numericPoint.provenance)}</span>
                    {numericPoint.source_excerpt && <blockquote>{numericPoint.source_excerpt}</blockquote>}
                    {numericPoint.view_source_path && <Link href={numericPoint.view_source_path}>View Source</Link>}
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
