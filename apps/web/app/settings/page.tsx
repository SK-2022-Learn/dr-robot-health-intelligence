"use client";

import { useCallback } from "react";

import { Card, EmptyState, ErrorState, LoadingState, PageHeading, StatusPill } from "@/components/ui";
import { getAuditLogs } from "@/lib/api/audit";
import { getSystemStatus } from "@/lib/api/system";
import { useResource } from "@/lib/hooks/use-resource";
import type { AuditLog } from "@/lib/types/api";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

type AuditActivityGroup = {
  latest: AuditLog;
  count: number;
};

export function groupRecentAuditActivity(entries: AuditLog[]): AuditActivityGroup[] {
  const groups = new Map<string, AuditActivityGroup>();

  for (const entry of entries) {
    const calendarDate = entry.created_at.slice(0, 10);
    const key = `${entry.action}\u0000${entry.entity_type}\u0000${calendarDate}`;
    const existing = groups.get(key);

    if (existing) {
      existing.count += 1;
    } else {
      groups.set(key, { latest: entry, count: 1 });
    }
  }

  return Array.from(groups.values());
}

export default function SettingsPage() {
  const systemLoader = useCallback((signal?: AbortSignal) => getSystemStatus(signal), []);
  const auditLoader = useCallback((signal?: AbortSignal) => getAuditLogs(signal), []);
  const system = useResource(systemLoader);
  const audit = useResource(auditLoader);
  const recentAudit = groupRecentAuditActivity(audit.data ?? []).slice(0, 8);
  return <><PageHeading eyebrow="System transparency" title="Settings" description="Non-sensitive runtime status and append-only activity history." />
    <div className="two-column"><Card title="System status">{system.loading ? <LoadingState /> : system.error ? <ErrorState message={system.error} /> : system.data && <div className="summary-stack">
      <div><span>Environment</span><strong>{system.data.environment}</strong></div>
      <div><span>SQLite</span><StatusPill tone={system.data.database === "connected" ? "good" : "warm"}>{friendlyLabel(system.data.database)}</StatusPill></div>
      <div><span>Upload directory</span><StatusPill tone={system.data.upload_directory === "configured" ? "good" : "warm"}>{friendlyLabel(system.data.upload_directory)}</StatusPill></div>
      <div><span>Pinecone</span><StatusPill tone={system.data.vector_status === "connected" ? "good" : "warm"}>{friendlyLabel(system.data.vector_status)}</StatusPill></div>
      <div><span>Index</span><strong>{system.data.vector_index}</strong></div>
      <div><span>Vector dimension</span><strong>{system.data.vector_dimension ?? "Unavailable"}</strong></div>
      <div><span>Metric</span><strong>{system.data.vector_metric ?? "Unavailable"}</strong></div>
      <div><span>Embedding Provider</span><strong>{system.data.embedding_provider}</strong></div>
      <div><span>Embedding Model</span><strong>{system.data.embedding_model}</strong></div>
      <div><span>Embedding Status</span><StatusPill tone={system.data.embedding_status === "connected" ? "good" : "warm"}>{friendlyLabel(system.data.embedding_status)}</StatusPill></div>
      <div><span>Compatibility</span><StatusPill tone={system.data.compatibility === "compatible" ? "good" : "warm"}>{system.data.compatibility === "compatible" ? "Compatible" : system.data.compatibility === "dimension_mismatch" ? "Dimension mismatch" : "Unavailable"}</StatusPill></div>
      <div><span>Ollama</span><StatusPill tone={system.data.llm === "connected" ? "good" : "warm"}>{system.data.llm === "connected" ? "Connected" : "Unavailable"}</StatusPill></div>
      <div><span>LLM Model</span><strong>{system.data.llm_model}</strong></div>
      <div><span>Safety Gate</span><StatusPill tone="good">Enabled</StatusPill></div>
      <div><span>Safety Version</span><strong>{system.data.safety_policy_version}</strong></div>
      <div><span>Agent Orchestration</span><StatusPill tone={system.data.agent_orchestration === "enabled" ? "good" : "warm"}>{friendlyLabel(system.data.agent_orchestration)}</StatusPill></div>
    </div>}</Card>
      <Card title="Privacy controls"><div className="compact-list"><div><strong>Profile isolation</strong><span>Profile-scoped endpoints validate each requested profile.</span></div><div><strong>Source traceability</strong><span>Stored records retain provenance and verification status.</span></div><div><strong>Cloud vector storage</strong><span>Indexed excerpts are stored in Pinecone; structured SQLite data remains local.</span></div><div><strong>Secrets</strong><span>Credentials and filesystem paths are never shown here.</span></div></div></Card></div>
    <Card title="Recent audit activity">{audit.loading ? <LoadingState /> : audit.error ? <ErrorState message={audit.error} /> : !recentAudit.length ? <EmptyState title="No audit activity" message="No audit entries are stored." /> : <div className="audit-list">{recentAudit.map(({ latest, count }) => <div key={latest.id}><span className="audit-action">{friendlyLabel(latest.action)}{count > 1 && <small className="audit-count">{count} occurrences</small>}</span><strong>{friendlyLabel(latest.entity_type)}</strong><time>{formatDate(latest.created_at)}</time></div>)}</div>}</Card>
  </>;
}
