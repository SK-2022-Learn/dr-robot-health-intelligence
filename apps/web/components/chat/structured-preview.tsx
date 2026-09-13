"use client";

import Link from "next/link";
import { useState } from "react";

import { ErrorState, StatusPill } from "@/components/ui";
import {
  clarifyPending,
  confirmPending,
  correctPending,
  rejectPending,
} from "@/lib/api/chat";
import { readableApiError } from "@/lib/api/client";
import type {
  ChatMessageResponse,
  DailyHealthExtraction,
  DailyObservation,
  PendingHealthEntry,
} from "@/lib/types/api";
import { friendlyLabel } from "@/lib/utils/format";

type Props = {
  pendingId: string;
  initial: DailyHealthExtraction;
  questions: ChatMessageResponse["questions"];
  onChanged: (pending: PendingHealthEntry) => void;
};

function dateTimeValue(value: string | null): string {
  return value ? value.slice(0, 16) : "";
}

function entryTitle(item: DailyObservation): string {
  if (item.entry_type === "glucose") return `${friendlyLabel(item.context)} glucose`;
  if (item.entry_type === "blood_pressure") return "Blood pressure";
  return "Weight";
}

export function StructuredPreview({ pendingId, initial, questions, onChanged }: Props) {
  const [extraction, setExtraction] = useState(initial);
  const [activeQuestions, setActiveQuestions] = useState(questions);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [discarded, setDiscarded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateObservation(index: number, changes: Partial<DailyObservation>) {
    setExtraction((current) => ({
      ...current,
      observations: current.observations.map((item, itemIndex) =>
        itemIndex === index ? ({ ...item, ...changes } as DailyObservation) : item,
      ),
    }));
  }

  async function answer(field: string, value: string) {
    setBusy(true);
    setError(null);
    try {
      const response = await clarifyPending(pendingId, { [field]: value });
      if (response.extraction) setExtraction(response.extraction);
      setActiveQuestions(response.questions);
    } catch (reason: unknown) {
      setError(readableApiError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveChanges() {
    setBusy(true);
    setError(null);
    try {
      const pending = await correctPending(pendingId, extraction);
      setExtraction(pending.extraction);
      setActiveQuestions(pending.extraction.clarifications);
      setEditing(false);
      onChanged(pending);
    } catch (reason: unknown) {
      setError(readableApiError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const result = await confirmPending(pendingId);
      setSaved(true);
      onChanged(result.pending);
    } catch (reason: unknown) {
      setError(readableApiError(reason));
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    setBusy(true);
    setError(null);
    try {
      const pending = await rejectPending(pendingId);
      setDiscarded(true);
      onChanged(pending);
    } catch (reason: unknown) {
      setError(readableApiError(reason));
    } finally {
      setBusy(false);
    }
  }

  if (saved) {
    return (
      <section className="chat-success" role="status">
        <strong>Saved to your health memory.</strong>
        <span>Confirmed records are now available in My Health and Timeline.</span>
        <div className="chat-links">
          <Link href="/my-health">Open My Health &rarr;</Link>
          <Link href="/timeline">Open Timeline &rarr;</Link>
        </div>
      </section>
    );
  }
  if (discarded) {
    return <section className="chat-discarded" role="status">Entry discarded. Nothing was added to health memory.</section>;
  }

  if (activeQuestions.length > 0) {
    return (
      <section className="clarification-panel">
        <p className="eyebrow">Clarification required</p>
        <h2>I need one detail before saving this.</h2>
        {activeQuestions.map((question) => (
          <div className="clarification-question" key={question.field}>
            <strong>{question.question}</strong>
            <div className="option-row">
              {question.options.map((option) => (
                <button key={option} disabled={busy} onClick={() => answer(question.field, option)}>
                  {friendlyLabel(option)}
                </button>
              ))}
            </div>
          </div>
        ))}
        <div className="candidate-actions">
          <button className="reject-button" disabled={busy} onClick={discard}>Discard</button>
        </div>
        {error && <ErrorState message={error} />}
      </section>
    );
  }

  return (
    <section className="structured-preview">
      <div className="preview-heading">
        <div>
          <p className="eyebrow">Pending review</p>
          <h2>Here is what I understood</h2>
        </div>
        <StatusPill tone="warm">Not saved yet</StatusPill>
      </div>
      <p className="helper-text">
        Chat text is not trusted health memory. Review these structured values before confirming.
      </p>

      <div className="preview-items">
        {extraction.observations.map((item, index) => (
          <article className="preview-item" key={`observation-${index}`}>
            <strong>{entryTitle(item)}</strong>
            {item.entry_type === "blood_pressure" ? (
              <span>{item.systolic}/{item.diastolic} {item.unit}</span>
            ) : (
              <span>{item.value} {item.unit ?? "Unit needed"}</span>
            )}
            {editing && (
              <div className="chat-edit-grid">
                {item.entry_type === "blood_pressure" ? (
                  <>
                    <label>Systolic<input aria-label={`Systolic ${index + 1}`} type="number" value={item.systolic} onChange={(event) => updateObservation(index, { systolic: Number(event.target.value) })} /></label>
                    <label>Diastolic<input aria-label={`Diastolic ${index + 1}`} type="number" value={item.diastolic} onChange={(event) => updateObservation(index, { diastolic: Number(event.target.value) })} /></label>
                  </>
                ) : (
                  <label>Value<input aria-label={`${entryTitle(item)} value`} type="number" step="any" value={item.value} onChange={(event) => updateObservation(index, { value: Number(event.target.value) })} /></label>
                )}
                {item.entry_type === "glucose" && <label>Context<select value={item.context} onChange={(event) => updateObservation(index, { context: event.target.value as typeof item.context })}><option value="FASTING">Fasting</option><option value="BEFORE_MEAL">Before meal</option><option value="AFTER_MEAL">After meal</option><option value="RANDOM">Random</option><option value="UNKNOWN">Unknown</option></select></label>}
                {item.entry_type === "glucose" && <label>Unit<select value={item.unit} onChange={(event) => updateObservation(index, { unit: event.target.value as typeof item.unit })}><option value="mg/dL">mg/dL</option><option value="mmol/L">mmol/L</option></select></label>}
                {item.entry_type === "weight" && <label>Unit<select value={item.unit ?? ""} onChange={(event) => updateObservation(index, { unit: (event.target.value || null) as typeof item.unit })}><option value="">Choose unit</option><option value="kg">kg</option><option value="lb">lb</option></select></label>}
                <label>Date/time<input type="datetime-local" value={dateTimeValue(item.observed_at)} onChange={(event) => updateObservation(index, { observed_at: event.target.value || null })} /></label>
              </div>
            )}
          </article>
        ))}

        {extraction.sleep_entries.map((item, index) => (
          <article className="preview-item" key={`sleep-${index}`}>
            <strong>Sleep</strong><span>{item.duration_minutes / 60} hours</span>
            {editing && <div className="chat-edit-grid"><label>Duration minutes<input aria-label={`Sleep duration ${index + 1}`} type="number" value={item.duration_minutes} onChange={(event) => setExtraction((current) => ({ ...current, sleep_entries: current.sleep_entries.map((entry, entryIndex) => entryIndex === index ? { ...entry, duration_minutes: Number(event.target.value) } : entry) }))} /></label><label>Sleep date<input type="date" value={item.sleep_date ?? ""} onChange={(event) => setExtraction((current) => ({ ...current, sleep_entries: current.sleep_entries.map((entry, entryIndex) => entryIndex === index ? { ...entry, sleep_date: event.target.value || null } : entry) }))} /></label><label>Quality<input value={item.quality ?? ""} onChange={(event) => setExtraction((current) => ({ ...current, sleep_entries: current.sleep_entries.map((entry, entryIndex) => entryIndex === index ? { ...entry, quality: event.target.value || null } : entry) }))} /></label></div>}
          </article>
        ))}

        {extraction.symptoms.map((item, index) => (
          <article className="preview-item" key={`symptom-${index}`}>
            <strong>Symptom: {item.name}</strong><span>{friendlyLabel(item.severity)}</span>
            {editing && <div className="chat-edit-grid"><label>Name<input value={item.name} onChange={(event) => setExtraction((current) => ({ ...current, symptoms: current.symptoms.map((entry, entryIndex) => entryIndex === index ? { ...entry, name: event.target.value } : entry) }))} /></label><label>Severity<select value={item.severity} onChange={(event) => setExtraction((current) => ({ ...current, symptoms: current.symptoms.map((entry, entryIndex) => entryIndex === index ? { ...entry, severity: event.target.value as typeof entry.severity } : entry) }))}><option value="MILD">Mild</option><option value="MODERATE">Moderate</option><option value="SEVERE">Severe</option><option value="UNKNOWN">Unknown</option></select></label><label>Started at<input type="datetime-local" value={dateTimeValue(item.started_at)} onChange={(event) => setExtraction((current) => ({ ...current, symptoms: current.symptoms.map((entry, entryIndex) => entryIndex === index ? { ...entry, started_at: event.target.value || null } : entry) }))} /></label><label>Duration<input value={item.duration_text ?? ""} onChange={(event) => setExtraction((current) => ({ ...current, symptoms: current.symptoms.map((entry, entryIndex) => entryIndex === index ? { ...entry, duration_text: event.target.value || null } : entry) }))} /></label></div>}
          </article>
        ))}

        {extraction.activities.map((item, index) => (
          <article className="preview-item" key={`activity-${index}`}>
            <strong>Activity: {item.activity_type}</strong>
            <span>{item.duration_minutes ? `${item.duration_minutes} minutes` : `${item.distance} ${item.distance_unit}`}</span>
            {editing && <div className="chat-edit-grid"><label>Activity<input value={item.activity_type} onChange={(event) => setExtraction((current) => ({ ...current, activities: current.activities.map((entry, entryIndex) => entryIndex === index ? { ...entry, activity_type: event.target.value } : entry) }))} /></label><label>Duration minutes<input type="number" value={item.duration_minutes ?? ""} onChange={(event) => setExtraction((current) => ({ ...current, activities: current.activities.map((entry, entryIndex) => entryIndex === index ? { ...entry, duration_minutes: event.target.value ? Number(event.target.value) : null } : entry) }))} /></label><label>Distance<input type="number" step="any" value={item.distance ?? ""} onChange={(event) => setExtraction((current) => ({ ...current, activities: current.activities.map((entry, entryIndex) => entryIndex === index ? { ...entry, distance: event.target.value ? Number(event.target.value) : null } : entry) }))} /></label><label>Distance unit<select value={item.distance_unit ?? ""} onChange={(event) => setExtraction((current) => ({ ...current, activities: current.activities.map((entry, entryIndex) => entryIndex === index ? { ...entry, distance_unit: (event.target.value || null) as typeof entry.distance_unit } : entry) }))}><option value="">None</option><option value="m">m</option><option value="km">km</option><option value="mi">mi</option></select></label><label>Date/time<input type="datetime-local" value={dateTimeValue(item.observed_at)} onChange={(event) => setExtraction((current) => ({ ...current, activities: current.activities.map((entry, entryIndex) => entryIndex === index ? { ...entry, observed_at: event.target.value || null } : entry) }))} /></label></div>}
          </article>
        ))}
      </div>

      {extraction.warnings.map((warning) => <p className="chat-warning" key={warning}>{warning}</p>)}
      {error && <ErrorState message={error} />}
      <div className="candidate-actions">
        {editing ? <button className="accept-button" disabled={busy} onClick={saveChanges}>Save changes</button> : <button className="accept-button" disabled={busy} onClick={confirm}>Confirm</button>}
        <button className="secondary-button" disabled={busy} onClick={() => setEditing((value) => !value)}>{editing ? "Cancel edit" : "Edit"}</button>
        <button className="reject-button" disabled={busy} onClick={discard}>Discard</button>
      </div>
    </section>
  );
}
