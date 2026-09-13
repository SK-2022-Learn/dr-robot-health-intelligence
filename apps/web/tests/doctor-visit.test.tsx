import { fireEvent, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DoctorVisitPage from "@/app/doctor-visit/page";
import { ProfileProvider } from "@/components/health/profile-context";
import { generateDoctorVisitBrief } from "@/lib/api/doctor-visit";
import { getProfiles } from "@/lib/api/profiles";
import { getTimelineEvidence } from "@/lib/api/timeline";
import type {
  DoctorVisitBrief,
  EvidenceResponse,
  Profile,
  TrendAnalysisResult,
  VisitEvidenceReference,
} from "@/lib/types/api";

vi.mock("next/link", () => ({
  default: (props: AnchorHTMLAttributes<HTMLAnchorElement>) => <a {...props} />,
}));
vi.mock("@/lib/api/profiles", () => ({ getProfiles: vi.fn() }));
vi.mock("@/lib/api/doctor-visit", () => ({ generateDoctorVisitBrief: vi.fn() }));
vi.mock("@/lib/api/timeline", () => ({ getTimelineEvidence: vi.fn() }));

const profile: Profile = {
  id: "visit-profile",
  owner_user_id: "owner",
  display_name: "Lakshmi Rao",
  relationship_to_owner: "SELF",
  date_of_birth: "1980-01-20",
  sex: null,
  access_level: "PRIVATE",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function reference(entityType: VisitEvidenceReference["entity_type"], id: string): VisitEvidenceReference {
  return {
    entity_type: entityType,
    entity_id: id,
    source_type: "DOCUMENT",
    source_label: "visit-source.pdf, page 1",
    provenance: "DOCUMENT_VERIFIED",
    verification_status: "VERIFIED",
    has_evidence: true,
    evidence_path: `/api/v1/profiles/${profile.id}/evidence/${entityType}/${id}`,
  };
}

const trend: TrendAnalysisResult = {
  profile_id: profile.id,
  metric: "glucose",
  metric_label: "Glucose",
  context: "AFTER_MEAL",
  unit: "mg/dL",
  reference_date: "2026-09-13",
  recent_period: { start: "2026-08-15", end: "2026-09-13", days: 30, boundaries: "inclusive" },
  baseline_period: { start: "2026-05-17", end: "2026-08-14", days: 90, boundaries: "inclusive" },
  recent_count: 5,
  baseline_count: 5,
  recent_summary: { count: 5, mean: 172, median: 172, minimum: 168, maximum: 176, standard_deviation: 2.6, first_value: 168, last_value: 173 },
  baseline_summary: { count: 5, mean: 148, median: 148, minimum: 145, maximum: 151, standard_deviation: 2, first_value: 145, last_value: 149 },
  absolute_change: 24,
  percent_change: 16.2162,
  classification: "INCREASED",
  confidence: "HIGH",
  confidence_reason: "Both periods have sufficient verified readings and time coverage.",
  missing_data: [],
  evidence_ids: ["baseline-1", "recent-1"],
  evidence: [
    {
      observation_id: "baseline-1",
      recorded_at: "2026-06-01T00:00:00Z",
      original_value: "145 mg/dL",
      normalized_value: 145,
      normalized_unit: "mg/dL",
      provenance: "DOCUMENT_VERIFIED",
      verification_status: "VERIFIED",
      source_type: "DOCUMENT",
      source_label: "visit-source.pdf, page 1",
      source_excerpt: "Post-meal glucose 145 mg/dL",
      view_source_path: "/uploads?document=doc-1&page=1",
      evidence_path: "/evidence/baseline-1",
    },
    {
      observation_id: "recent-1",
      recorded_at: "2026-09-01T00:00:00Z",
      original_value: "168 mg/dL",
      normalized_value: 168,
      normalized_unit: "mg/dL",
      provenance: "DOCUMENT_VERIFIED",
      verification_status: "VERIFIED",
      source_type: "DOCUMENT",
      source_label: "visit-source.pdf, page 1",
      source_excerpt: "Post-meal glucose 168 mg/dL",
      view_source_path: "/uploads?document=doc-1&page=1",
      evidence_path: "/evidence/recent-1",
    },
  ],
  calculation_version: "numeric-trend-v1",
  stability_threshold_percent: 5,
  explanation: "Recent after meal glucose averaged 172 mg/dL versus 148 mg/dL in the personal baseline.",
  explanation_source: "TEMPLATE",
  display_priority: 1,
};

const brief: DoctorVisitBrief = {
  profile_id: profile.id,
  profile_display_name: profile.display_name,
  profile_age: 46,
  date_of_birth: profile.date_of_birth,
  relationship_to_owner: "SELF",
  generated_at: "2026-09-13T10:00:00Z",
  data_cutoff: "2026-09-12T00:00:00Z",
  summary_version: "doctor-visit-v1",
  overview: "This brief summarizes trusted records for the visit.",
  overview_source: "TEMPLATE",
  rewrite_status: "NOT_REQUESTED",
  known_history: [{
    record_id: "condition-1",
    title: "Diabetes",
    timeline_type: "CONDITION",
    documented_date: "2018-02-01T00:00:00Z",
    end_date: null,
    evidence: reference("health_event", "condition-1"),
  }],
  recent_changes: [{ key: "glucose:AFTER_MEAL", statement: trend.explanation, analysis: trend }],
  medications: [{
    record_id: "medication-1",
    name: "Metformin",
    dose: "500",
    dose_unit: "mg",
    frequency: "twice daily",
    route: null,
    start_date: "2022-01-01",
    end_date: null,
    last_updated_at: "2026-09-01T00:00:00Z",
    reconciliation_needed: true,
    evidence: reference("medication", "medication-1"),
  }],
  recent_labs: [{
    record_id: "lab-1",
    name: "HbA1c",
    value: "7.2",
    unit: "%",
    observed_at: "2026-09-11T00:00:00Z",
    interpretation: null,
    evidence: reference("observation", "lab-1"),
  }],
  recent_measurements: [{
    record_id: "measure-1",
    name: "Blood pressure",
    value: "126",
    unit: "mmHg",
    observed_at: "2026-09-12T00:00:00Z",
    interpretation: null,
    evidence: reference("observation", "measure-1"),
  }],
  recent_symptoms: [{
    name: "Constipation",
    report_count: 3,
    most_recent: "2026-09-12T00:00:00Z",
    statement: "Constipation was reported 3 time(s) in the recent 30-day period.",
    evidence: [reference("symptom", "symptom-1")],
  }],
  missing_evidence: [{
    type: "MISSING_RECENT_THYROID_LAB",
    message: "No recent thyroid lab is recorded for this profile.",
    entity_type: null,
    entity_id: null,
  }],
  questions_to_discuss: [{
    question_id: "VISIT-Q-THYROID-001",
    trigger: "MISSING_RECENT_LAB",
    question: "Would updated thyroid testing be useful to discuss?",
  }],
  evidence_summary: [
    { key: "VERIFIED_DOCUMENT_SOURCES", label: "Verified document sources", count: 1 },
    { key: "USER_REPORTED_ITEMS", label: "User-reported items", count: 3 },
    { key: "MISSING_EVIDENCE_ITEMS", label: "Missing evidence items", count: 1 },
    { key: "UNVERIFIED_ITEMS", label: "Unverified items excluded", count: 2 },
  ],
  safety_notes: [
    "This brief summarizes trusted records for discussion with a healthcare professional.",
    "It does not diagnose, prescribe, or recommend medication changes.",
  ],
};

const evidence: EvidenceResponse = {
  profile_id: profile.id,
  entity_id: "condition-1",
  entity_type: "health_event",
  source_type: "DOCUMENT",
  provenance: "DOCUMENT_VERIFIED",
  verification_status: "VERIFIED",
  source: {
    type: "DOCUMENT",
    document_id: "doc-1",
    filename: "visit-source.pdf",
    document_date: "2026-09-11",
    page_number: 1,
    excerpt: "Diabetes documented.",
    page_text: "Visit source record: Diabetes documented.",
    view_source_path: "/uploads?document=doc-1&page=1",
  },
  saved_value: "Diabetes",
  correction_history: [],
};

function renderPage() {
  return render(<ProfileProvider><DoctorVisitPage /></ProfileProvider>);
}

beforeEach(() => {
  vi.mocked(getProfiles).mockResolvedValue([profile]);
  vi.mocked(generateDoctorVisitBrief).mockResolvedValue(brief);
  vi.mocked(getTimelineEvidence).mockResolvedValue(evidence);
});

describe("Phase 12 Doctor Visit Brief UI", () => {
  it("renders every factual, gap, question, and evidence section", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Doctor Visit Brief — Lakshmi Rao" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Known History" })).toBeInTheDocument();
    for (const heading of [
      "Recent Changes",
      "Current Medications",
      "Recent Labs",
      "Recent Measurements",
      "Recent Symptoms",
      "Missing Evidence",
      "Questions to Discuss",
      "Evidence Summary",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
    expect(screen.getByText("Metformin")).toBeInTheDocument();
    expect(screen.getByText("7.2 %")).toBeInTheDocument();
    expect(screen.getByText(/reported 3 time/)).toBeInTheDocument();
    expect(screen.getByText("Would updated thyroid testing be useful to discuss?")).toBeInTheDocument();
    expect(screen.queryByText(/diagnosis:/i)).not.toBeInTheDocument();
  });

  it("opens exact source evidence for a factual item", async () => {
    renderPage();
    fireEvent.click((await screen.findAllByRole("button", { name: "View Evidence" }))[0]);
    expect(await screen.findByText("Where this fact came from")).toBeInTheDocument();
    expect(screen.getByText("Diabetes documented.")).toBeInTheDocument();
    expect(getTimelineEvidence).toHaveBeenCalledWith(
      profile.id,
      "health_event",
      "condition-1",
    );
  });

  it("opens the reused deterministic calculation from WHY", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "WHY?" }));
    expect(await screen.findByText("HOW IT WAS CALCULATED")).toBeInTheDocument();
    expect(screen.getByText(/Recent mean 172 mg\/dL minus baseline mean 148 mg\/dL/)).toBeInTheDocument();
    expect(screen.getByText("numeric-trend-v1")).toBeInTheDocument();
  });

  it("invokes the browser print workflow", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Print / Save as PDF" }));
    expect(print).toHaveBeenCalledOnce();
  });

  it("shows explicit empty states without invented values", async () => {
    vi.mocked(generateDoctorVisitBrief).mockResolvedValue({
      ...brief,
      overview: "This brief summarizes 0 known history item(s), 0 current medication(s), 0 recent lab result(s), and 0 supported recent change(s) from trusted records.",
      known_history: [],
      recent_changes: [],
      medications: [],
      recent_labs: [],
      recent_measurements: [],
      recent_symptoms: [],
      missing_evidence: [],
      questions_to_discuss: [],
    });
    renderPage();
    expect(await screen.findByText("No known history recorded")).toBeInTheDocument();
    expect(screen.getByText("No current medications recorded")).toBeInTheDocument();
    expect(screen.getByText("No recent labs recorded")).toBeInTheDocument();
    expect(screen.getByText("No questions generated")).toBeInTheDocument();
    expect(screen.queryByText("Metformin")).not.toBeInTheDocument();
  });

  it("shows an API failure state", async () => {
    vi.mocked(generateDoctorVisitBrief).mockRejectedValue(new Error("offline"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });
});
