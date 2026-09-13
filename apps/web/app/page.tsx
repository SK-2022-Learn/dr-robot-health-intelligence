"use client";

import { useCallback } from "react";

import { useProfile } from "@/components/health/profile-context";
import { Card, Disclaimer, EmptyState, ErrorState, LoadingState, PageHeading, StatusPill } from "@/components/ui";
import { getProfileSnapshot } from "@/lib/api/profile-data";
import { useResource } from "@/lib/hooks/use-resource";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

export default function Home() {
  const { activeProfile, loading: profilesLoading, error: profileError } = useProfile();
  const loader = useCallback((signal?: AbortSignal) => getProfileSnapshot(activeProfile!.id, signal), [activeProfile]);
  const snapshot = useResource(loader, activeProfile?.id ?? null);

  if (profilesLoading || (!activeProfile && !profileError)) return <LoadingState label="Preparing your health overview…" />;
  if (profileError) return <ErrorState message={profileError} />;
  if (!activeProfile) return <EmptyState title="No health profile yet" message="Create a profile through the API to begin organizing a health history." />;

  const recent = snapshot.data?.events.slice(0, 3) ?? [];
  return <>
    <PageHeading eyebrow="Health overview" title={`Welcome, ${activeProfile.display_name}`} description="A clear view of the health records currently stored for this profile." />
    {snapshot.loading ? <LoadingState /> : snapshot.error ? <ErrorState message={snapshot.error} /> : snapshot.data && <>
      <div className="metric-grid">
        <Card className="metric-card"><span className="metric-icon teal">◷</span><strong>{snapshot.data.events.length}</strong><span>Timeline events</span></Card>
        <Card className="metric-card"><span className="metric-icon blue">◇</span><strong>{snapshot.data.observations.length}</strong><span>Observations</span></Card>
        <Card className="metric-card"><span className="metric-icon orange">▤</span><strong>{snapshot.data.documents.length}</strong><span>Source documents</span></Card>
        <Card className="metric-card"><span className="metric-icon purple">✚</span><strong>{snapshot.data.medications.filter((item) => item.is_active).length}</strong><span>Active medications</span></Card>
      </div>
      <div className="two-column">
        <Card title="Recent health history" action={<a className="text-link" href="/timeline">View timeline →</a>}>
          {recent.length === 0 ? <EmptyState title="No events recorded" message="Stored health events will appear here in chronological order." /> : <div className="item-list">{recent.map((event) => <article className="list-item" key={event.id}><span className="timeline-dot" /><div><strong>{event.title}</strong><p>{friendlyLabel(event.event_type)} · {formatDate(event.event_date)}</p></div><StatusPill tone={event.verification_status === "VERIFIED" ? "good" : "warm"}>{friendlyLabel(event.verification_status)}</StatusPill></article>)}</div>}
        </Card>
        <Card title="Record completeness"><div className="summary-stack"><div><span>Symptoms</span><strong>{snapshot.data.symptoms.length}</strong></div><div><span>Medications</span><strong>{snapshot.data.medications.length}</strong></div><div><span>Observations</span><strong>{snapshot.data.observations.length}</strong></div></div><p className="helper-text">Counts reflect stored records only and are not a clinical assessment.</p></Card>
      </div>
      <div className="two-column">
        <Card title="Recent observations">
          {snapshot.data.observations.length === 0 ? <EmptyState title="No observations available" message="Stored measurements and results will appear here." /> : <div className="compact-list">{snapshot.data.observations.slice(0, 3).map((item) => <div key={item.id}><strong>{item.display_name}</strong><span>{item.value_number ?? item.value_text ?? "Recorded"} {item.unit ?? ""} · {formatDate(item.observed_at)}</span></div>)}</div>}
        </Card>
        <Card title="Explore your record"><div className="quick-links"><a href="/my-health">My Health <span>→</span></a><a href="/uploads">Upload Records <span>→</span></a><a href="/timeline">Timeline <span>→</span></a><a href="/family">Family <span>→</span></a><a href="/insights">Insights <span>→</span></a><a href="/doctor-visit">Doctor Visit <span>→</span></a></div></Card>
      </div>
    </>}
    <Disclaimer />
  </>;
}
