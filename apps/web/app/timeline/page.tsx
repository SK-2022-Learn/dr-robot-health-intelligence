"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { useProfile } from "@/components/health/profile-context";
import { EvidencePanel } from "@/components/timeline/evidence-panel";
import { Card, EmptyState, ErrorState, LoadingState, PageHeading, StatusPill } from "@/components/ui";
import { readableApiError } from "@/lib/api/client";
import { getMissingEvidence, getTimeline, getTimelineEvidence } from "@/lib/api/timeline";
import { useResource } from "@/lib/hooks/use-resource";
import type { EvidenceResponse, TimelineItem, TimelineType } from "@/lib/types/api";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

const filters: Array<{ label: string; value: TimelineType | null }> = [
  { label: "All", value: null },
  { label: "Conditions", value: "CONDITION" },
  { label: "Labs", value: "LAB" },
  { label: "Measurements", value: "MEASUREMENT" },
  { label: "Medications", value: "MEDICATION" },
  { label: "Symptoms", value: "SYMPTOM" },
];

const provenanceLabels: Record<TimelineItem["provenance"], string> = {
  DOCUMENT_VERIFIED: "Document Verified",
  AI_EXTRACTED: "AI Extracted + Reviewed",
  USER_REPORTED: "User Reported",
  USER_CORRECTED: "User Corrected",
  DEVICE_MEASURED: "Device Measured",
  AI_DERIVED: "AI Derived",
};

function groupLabel(item: TimelineItem): string {
  if (!item.occurred_at) return "Date unavailable";
  const parsed = new Date(item.occurred_at);
  return Number.isNaN(parsed.valueOf()) ? "Date unavailable" : String(parsed.getFullYear());
}

export default function TimelinePage() {
  const { activeProfile, loading, error } = useProfile();
  const [filter, setFilter] = useState<TimelineType | null>(null);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  const timelineLoader = useCallback(
    (signal?: AbortSignal) => getTimeline(activeProfile!.id, filter, "desc", signal),
    [activeProfile, filter],
  );
  const gapLoader = useCallback(
    (signal?: AbortSignal) => getMissingEvidence(activeProfile!.id, signal),
    [activeProfile],
  );
  const timeline = useResource(
    timelineLoader,
    activeProfile ? `${activeProfile.id}:${filter ?? "ALL"}` : null,
  );
  const gaps = useResource(gapLoader, activeProfile?.id ?? null);
  const groups = useMemo(() => {
    const result = new Map<string, TimelineItem[]>();
    for (const item of timeline.data?.items ?? []) {
      const label = groupLabel(item);
      result.set(label, [...(result.get(label) ?? []), item]);
    }
    return [...result.entries()];
  }, [timeline.data]);

  async function explain(item: TimelineItem) {
    if (!activeProfile) return;
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(true);
    try {
      setEvidence(await getTimelineEvidence(activeProfile.id, item.entity_type, item.entity_id));
    } catch (reason: unknown) {
      setEvidenceError(readableApiError(reason));
    } finally {
      setEvidenceLoading(false);
    }
  }

  if (loading) return <LoadingState label="Loading profile..." />;
  if (error) return <ErrorState message={error} />;
  if (!activeProfile) {
    return <EmptyState title="No profile selected" message="Choose a profile to view its trusted timeline." />;
  }

  return (
    <>
      <PageHeading
        eyebrow="Longitudinal record"
        title="Timeline"
        description="Trusted health memory in clinical-date order, with provenance and source traceability."
      />

      <div className="timeline-filters" aria-label="Timeline filters">
        {filters.map((option) => (
          <button
            className={filter === option.value ? "active" : ""}
            key={option.label}
            onClick={() => setFilter(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="timeline-layout">
        <div className="timeline-main">
          <Card>
            {timeline.loading ? <LoadingState label="Building the trusted timeline..." /> : timeline.error ? (
              <ErrorState message={timeline.error} />
            ) : groups.length === 0 ? (
              <EmptyState title="No timeline entries" message="No trusted records match this view." />
            ) : groups.map(([label, items]) => (
              <section className="timeline-group" key={label}>
                <h2>{label}</h2>
                <div className="timeline">
                  {items.map((item) => (
                    <article key={item.id} className="timeline-entry">
                      <div className="timeline-date">{formatDate(item.occurred_at)}</div>
                      <span className="timeline-node" />
                      <div className="timeline-body">
                        <div>
                          <span className="eyebrow">{friendlyLabel(item.timeline_type)}</span>
                          <h3>{item.title}</h3>
                        </div>
                        {item.description && <p>{item.description}</p>}
                        <div className="pill-row">
                          <StatusPill tone={item.verification_status === "VERIFIED" ? "good" : "warm"}>
                            {friendlyLabel(item.verification_status)}
                          </StatusPill>
                          <StatusPill>{provenanceLabels[item.provenance]}</StatusPill>
                          <StatusPill tone={item.has_evidence ? "good" : "warm"}>
                            {friendlyLabel(item.source_type)} source
                          </StatusPill>
                          {item.has_correction && <StatusPill tone="warm">Corrected</StatusPill>}
                        </div>
                        <div className="timeline-actions">
                          <button onClick={() => explain(item)}>WHY?</button>
                          {item.source_document_id && (
                            <Link href={`/uploads?document=${encodeURIComponent(item.source_document_id)}`}>
                              View Source
                            </Link>
                          )}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </Card>

          <Card title="Missing Evidence" className="missing-evidence">
            <p className="helper-text">Structural record gaps only. These notices are not clinical recommendations.</p>
            {gaps.loading ? <LoadingState label="Checking record links..." /> : gaps.error ? (
              <ErrorState message={gaps.error} />
            ) : !gaps.data?.gaps.length ? (
              <EmptyState title="No structural gaps found" message="All visible records have the expected basic source and date fields." />
            ) : (
              <div className="gap-list">
                {gaps.data.gaps.map((gap) => (
                  <div key={`${gap.type}-${gap.entity_id}`}>
                    <StatusPill tone="warm">{friendlyLabel(gap.type)}</StatusPill>
                    <span>{gap.message}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {(evidenceLoading || evidenceError || evidence) && (
          <EvidencePanel
            evidence={evidence}
            loading={evidenceLoading}
            error={evidenceError}
            onClose={() => { setEvidence(null); setEvidenceError(null); }}
          />
        )}
      </div>
    </>
  );
}
