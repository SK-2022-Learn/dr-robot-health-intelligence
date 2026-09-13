import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TimelinePage from "@/app/timeline/page";
import { ProfileProvider } from "@/components/health/profile-context";
import { getProfiles } from "@/lib/api/profiles";
import { getMissingEvidence, getTimeline, getTimelineEvidence } from "@/lib/api/timeline";
import type { EvidenceResponse, Profile, TimelineItem, TimelineResponse } from "@/lib/types/api";

vi.mock("next/link", () => ({
  default: (props: AnchorHTMLAttributes<HTMLAnchorElement>) => <a {...props} />,
}));
vi.mock("@/lib/api/profiles", () => ({ getProfiles: vi.fn() }));
vi.mock("@/lib/api/timeline", () => ({
  getTimeline: vi.fn(),
  getMissingEvidence: vi.fn(),
  getTimelineEvidence: vi.fn(),
}));

const profile: Profile = {
  id: "profile-a",
  owner_user_id: "owner",
  display_name: "Alex Example",
  relationship_to_owner: "SELF",
  date_of_birth: null,
  sex: null,
  access_level: "PRIVATE",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const items: TimelineItem[] = [
  {
    id: "observation:lab-1",
    entity_id: "lab-1",
    entity_type: "observation",
    timeline_type: "LAB",
    title: "HbA1c",
    description: "7.2 %",
    occurred_at: "2026-09-01T00:00:00Z",
    end_at: null,
    date_precision: "EXACT",
    provenance: "AI_EXTRACTED",
    verification_status: "VERIFIED",
    confidence: null,
    source_type: "DOCUMENT",
    source_document_id: "document-1",
    source_message_id: null,
    has_evidence: true,
    has_correction: false,
    created_at: "2026-09-01T00:00:00Z",
  },
  {
    id: "observation:chat-1",
    entity_id: "chat-1",
    entity_type: "observation",
    timeline_type: "MEASUREMENT",
    title: "Glucose",
    description: "118 mg/dL",
    occurred_at: "2026-08-01T08:00:00Z",
    end_at: null,
    date_precision: "EXACT",
    provenance: "USER_CORRECTED",
    verification_status: "VERIFIED",
    confidence: null,
    source_type: "CHAT",
    source_document_id: null,
    source_message_id: "message-1",
    has_evidence: true,
    has_correction: true,
    created_at: "2026-08-01T08:00:00Z",
  },
];

const timeline: TimelineResponse = {
  profile_id: profile.id,
  items,
  total: items.length,
  limit: 100,
  offset: 0,
};

const documentEvidence: EvidenceResponse = {
  profile_id: profile.id,
  entity_id: "lab-1",
  entity_type: "observation",
  source_type: "DOCUMENT",
  provenance: "AI_EXTRACTED",
  verification_status: "VERIFIED",
  source: {
    type: "DOCUMENT",
    document_id: "document-1",
    filename: "synthetic-hba1c.txt",
    document_date: "2026-09-01",
    page_number: 2,
    excerpt: "HbA1c 7.2%",
    page_text: "Laboratory report\nHbA1c 7.2%",
    view_source_path: "/uploads?document=document-1&page=2",
  },
  saved_value: "7.2 %",
  correction_history: [],
};

const chatEvidence: EvidenceResponse = {
  profile_id: profile.id,
  entity_id: "chat-1",
  entity_type: "observation",
  source_type: "CHAT",
  provenance: "USER_CORRECTED",
  verification_status: "VERIFIED",
  source: {
    type: "CHAT",
    conversation_id: "conversation-1",
    message_id: "message-1",
    message: "Fasting glucose 181 mg/dL",
    message_timestamp: "2026-08-01T08:00:00Z",
    label: "USER-REPORTED SOURCE",
  },
  saved_value: "118 mg/dL",
  correction_history: [{
    action: "CHAT_ENTRY_CORRECTED",
    original_value: "181 mg/dL",
    corrected_value: "118 mg/dL",
    changed_fields: ["observations.0.value"],
    corrected_at: "2026-08-01T08:01:00Z",
    actor: "test-user",
  }],
};

function renderTimeline() {
  return render(<ProfileProvider><TimelinePage /></ProfileProvider>);
}

beforeEach(() => {
  vi.mocked(getProfiles).mockResolvedValue([profile]);
  vi.mocked(getTimeline).mockResolvedValue(timeline);
  vi.mocked(getMissingEvidence).mockResolvedValue({
    profile_id: profile.id,
    gaps: [{
      type: "MISSING_SOURCE",
      entity_type: "health_event",
      entity_id: "event-1",
      message: "No supporting source is linked to this record.",
    }],
  });
  vi.mocked(getTimelineEvidence).mockImplementation(async (_profileId, _type, entityId) => (
    entityId === "lab-1" ? documentEvidence : chatEvidence
  ));
});

describe("Phase 8 timeline evidence UI", () => {
  it("renders normalized items, badges, grouping, and neutral missing evidence", async () => {
    renderTimeline();
    expect(await screen.findByRole("heading", { name: "HbA1c" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Glucose" })).toBeInTheDocument();
    expect(screen.getByText("AI Extracted + Reviewed")).toBeInTheDocument();
    expect(screen.getByText("User Corrected")).toBeInTheDocument();
    expect(screen.getByText("No supporting source is linked to this record.")).toBeInTheDocument();
    expect(screen.getByText("2026")).toBeInTheDocument();
  });

  it("requests server-side filters", async () => {
    renderTimeline();
    await screen.findByRole("heading", { name: "HbA1c" });
    fireEvent.click(screen.getByRole("button", { name: "Labs" }));
    await waitFor(() => expect(getTimeline).toHaveBeenLastCalledWith(
      profile.id,
      "LAB",
      "desc",
      expect.any(AbortSignal),
    ));
  });

  it("opens document evidence with exact page and source navigation", async () => {
    renderTimeline();
    const whyButtons = await screen.findAllByRole("button", { name: "WHY?" });
    fireEvent.click(whyButtons[0]);
    expect(await screen.findByText("synthetic-hba1c.txt")).toBeInTheDocument();
    expect(screen.getByText("HbA1c 7.2%")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: "View Source" }).some(
        (link) => link.getAttribute("href") === "/uploads?document=document-1&page=2",
      ),
    ).toBe(true);
  });

  it("shows original chat text, saved value, and audit-backed correction history", async () => {
    renderTimeline();
    const whyButtons = await screen.findAllByRole("button", { name: "WHY?" });
    fireEvent.click(whyButtons[1]);
    expect(await screen.findByText("Fasting glucose 181 mg/dL")).toBeInTheDocument();
    expect(screen.getAllByText("118 mg/dL").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Original")).toBeInTheDocument();
    expect(screen.getAllByText("Corrected").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Observations\.0\.value/i)).toBeInTheDocument();
  });
});
