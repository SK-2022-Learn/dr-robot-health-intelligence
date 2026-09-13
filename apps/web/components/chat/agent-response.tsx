"use client";

import Link from "next/link";

import { Card, StatusPill } from "@/components/ui";
import { apiAbsoluteUrl, isRecord } from "@/lib/api/client";
import type { AskResponse } from "@/lib/types/api";
import { friendlyLabel } from "@/lib/utils/format";

function analyticsCard(result: Record<string, unknown>) {
  const metric = typeof result.metric_label === "string" ? result.metric_label : null;
  const classification = typeof result.classification === "string" ? result.classification : null;
  if (!metric || !classification) return null;
  const recent = isRecord(result.recent_summary) ? result.recent_summary : null;
  const baseline = isRecord(result.baseline_summary) ? result.baseline_summary : null;
  return (
    <div className="agent-result-grid">
      <div><span>Metric</span><strong>{metric}</strong></div>
      <div><span>Result</span><strong>{friendlyLabel(classification)}</strong></div>
      <div><span>Recent mean</span><strong>{String(recent?.mean ?? "Insufficient data")}</strong></div>
      <div><span>Baseline mean</span><strong>{String(baseline?.mean ?? "Insufficient data")}</strong></div>
    </div>
  );
}

function structuredCards(response: AskResponse) {
  const result = response.structured_result;
  if (!result) return null;
  const analytics = analyticsCard(result);
  if (analytics) return analytics;
  if (Array.isArray(result.results) && result.results.length && isRecord(result.results[0])) {
    return analyticsCard(result.results[0]);
  }
  if (Array.isArray(result.patterns)) {
    return (
      <div className="agent-result-list">
        {result.patterns.slice(0, 3).filter(isRecord).map((pattern, index) => (
          <div key={`${String(pattern.condition_name)}-${index}`}>
            <strong>{String(pattern.condition_name ?? "Family pattern")}</strong>
            <span>{String(pattern.statement ?? "Permission-scoped family result")}</span>
          </div>
        ))}
      </div>
    );
  }
  if (result.kind === "doctor_visit") {
    return <Link className="agent-deep-link" href="/doctor-visit">Open the complete Doctor Visit brief →</Link>;
  }
  const items = Array.isArray(result.items) ? result.items.filter(isRecord) : [];
  if (items.length) {
    return (
      <div className="agent-result-list">
        {items.slice(0, 4).map((item, index) => (
          <div key={`${String(item.id)}-${index}`}>
            <strong>{String(item.title ?? "Trusted record")}</strong>
            <span>{String(item.description ?? item.occurred_at ?? "Recorded")}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export function AgentResponse({ response }: { response: AskResponse }) {
  const urgent = response.safety?.decision === "ESCALATE";
  const blocked = response.safety?.decision === "BLOCK";
  return (
    <Card className="agent-response-card">
      <div className="agent-response-head">
        <div><span>Routed as</span><strong>{friendlyLabel(response.intent)}</strong></div>
        <StatusPill tone={urgent || blocked ? "warm" : "good"}>
          {urgent ? "Urgent" : blocked ? "Safety boundary" : "Checked"}
        </StatusPill>
      </div>
      <p className={urgent ? "agent-answer urgent" : "agent-answer"} role={urgent ? "alert" : "status"}>
        {response.answer}
      </p>
      {structuredCards(response)}
      {response.warnings.map((warning) => <p className="chat-warning" key={warning}>{warning}</p>)}
      {(response.sources.length > 0 || response.actions.length > 0) && (
        <details className="agent-why">
          <summary>WHY / sources</summary>
          {response.actions.length > 0 && (
            <p><strong>Used:</strong> {response.actions.map(friendlyLabel).join(" · ")}</p>
          )}
          {response.sources.length > 0 && (
            <ul>
              {response.sources.map((source, index) => (
                <li key={`${source.entity_id ?? source.document_id ?? source.label}-${index}`}>
                  {source.evidence_path ? (
                    <a href={apiAbsoluteUrl(source.evidence_path)} target="_blank" rel="noreferrer">
                      {source.label}{source.page_number ? ` · page ${source.page_number}` : ""}
                    </a>
                  ) : source.label}
                </li>
              ))}
            </ul>
          )}
          {response.nodes_run && <small>Operations: {response.nodes_run.map(friendlyLabel).join(" → ")}</small>}
        </details>
      )}
    </Card>
  );
}
