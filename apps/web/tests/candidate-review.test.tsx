import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CandidateReview } from "@/components/extraction/candidate-review";
import {
  acceptCandidate,
  correctCandidate,
  extractDocument,
  getCandidates,
  rejectCandidate,
} from "@/lib/api/extraction";
import type { ExtractedCandidate, SourceDocument } from "@/lib/types/api";

vi.mock("@/lib/api/extraction", () => ({
  acceptCandidate: vi.fn(),
  correctCandidate: vi.fn(),
  extractDocument: vi.fn(),
  getCandidates: vi.fn(),
  rejectCandidate: vi.fn(),
}));

const document: SourceDocument = {
  id: "document-review",
  profile_id: "profile-review",
  original_filename: "synthetic-review.txt",
  mime_type: "text/plain",
  document_date: "2026-09-01",
  status: "PARSED",
  page_count: 1,
  has_extracted_text: true,
  vector_index_status: "NOT_INDEXED",
  vector_indexed_at: null,
  vector_chunk_count: 0,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

function candidate(
  id: string,
  type: ExtractedCandidate["candidate_type"],
  data: Record<string, unknown>,
  confidence = 0.9,
): ExtractedCandidate {
  return {
    id,
    document_id: document.id,
    candidate_type: type,
    structured_data: { ...data, confidence, evidence_text: `Evidence for ${id}`, page_number: 1 },
    confidence,
    status: "PENDING",
    evidence_text: `Evidence for ${id}`,
    page_number: 1,
    reviewed_by_user_id: null,
    reviewed_at: null,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  };
}

const lab = candidate("lab-1", "lab", {
  test_name: "Fasting glucose",
  value_number: 181,
  value_text: null,
  unit: "mg/dL",
  reference_low: null,
  reference_high: null,
  reference_range_text: null,
  collected_date: "2026-09-01",
  interpretation: null,
});
const symptom = candidate("symptom-1", "symptom", {
  name: "Constipation",
  severity: "mild",
  started_at: null,
  ended_at: null,
  notes: null,
}, 0.52);

beforeEach(() => {
  vi.mocked(getCandidates).mockResolvedValue([]);
  vi.mocked(extractDocument).mockResolvedValue({
    document_id: document.id,
    status: "completed",
    candidate_count: 2,
    by_type: { lab: 1, symptom: 1 },
    reused_existing: false,
  });
});

describe("candidate review", () => {
  it("extracts candidates, then opens a grouped evidence review", async () => {
    vi.mocked(getCandidates).mockResolvedValueOnce([]).mockResolvedValueOnce([lab, symptom]);
    render(<CandidateReview document={document} />);
    await waitFor(() => expect(getCandidates).toHaveBeenCalledWith(document.id));

    fireEvent.click(screen.getByRole("button", { name: "Extract Health Facts" }));
    expect(screen.getByRole("button", { name: "Extracting…" })).toBeDisabled();
    expect(await screen.findByText("2 untrusted candidates ready for review.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Review" }));

    expect(screen.getByRole("heading", { name: "Labs" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Symptoms" })).toBeInTheDocument();
    expect(screen.getByText("Evidence for lab-1", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText("Source page: 1")).toHaveLength(2);
    expect(screen.getByText("High (90%)")).toBeInTheDocument();
    expect(screen.getByText("Low (52%)")).toBeInTheDocument();
    expect(screen.getAllByText("Extraction confidence")).toHaveLength(2);
  });

  it("accepts and rejects without a page refresh", async () => {
    vi.mocked(getCandidates).mockResolvedValue([lab, symptom]);
    vi.mocked(acceptCandidate).mockResolvedValue({
      candidate: { ...lab, status: "ACCEPTED" },
      trusted_record: { record_type: "observations", record_id: "observation-1" },
    });
    vi.mocked(rejectCandidate).mockResolvedValue({
      candidate: { ...symptom, status: "REJECTED" },
      trusted_record: null,
    });
    render(<CandidateReview document={document} />);
    fireEvent.click(await screen.findByRole("button", { name: "Open Review" }));

    const cards = documentCards();
    fireEvent.click(within(cards[0]).getByRole("button", { name: "Accept" }));
    expect(await within(cards[0]).findByText("Accepted")).toBeInTheDocument();
    fireEvent.click(within(cards[1]).getByRole("button", { name: "Reject" }));
    expect(await within(cards[1]).findByText("Rejected")).toBeInTheDocument();
  });

  it("corrects 181 to 118 while sending only editable structured fields", async () => {
    vi.mocked(getCandidates).mockResolvedValue([lab]);
    vi.mocked(correctCandidate).mockResolvedValue({
      candidate: { ...lab, status: "CORRECTED" },
      trusted_record: { record_type: "observations", record_id: "observation-2" },
    });
    render(<CandidateReview document={document} />);
    fireEvent.click(await screen.findByRole("button", { name: "Open Review" }));
    fireEvent.click(screen.getByRole("button", { name: "Correct / Edit" }));
    const input = screen.getByLabelText("Correct Value Number");
    fireEvent.change(input, { target: { value: "118" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Correction" }));

    await waitFor(() => expect(correctCandidate).toHaveBeenCalledWith(
      lab.id,
      expect.objectContaining({ value_number: 118 }),
    ));
    expect(await screen.findByText("Corrected")).toBeInTheDocument();
  });

  it("shows a controlled retry state when extraction fails", async () => {
    vi.mocked(extractDocument).mockRejectedValue(new Error("provider failed"));
    render(<CandidateReview document={document} />);
    await waitFor(() => expect(getCandidates).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "Extract Health Facts" }));
    expect(await screen.findByText("Structured extraction could not be completed.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry extraction" })).toBeInTheDocument();
  });
});

function documentCards(): HTMLElement[] {
  return screen.getAllByRole("article");
}
