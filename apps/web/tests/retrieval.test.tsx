import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SearchPage from "@/app/search/page";
import { ProfileProvider } from "@/components/health/profile-context";
import { DocumentIndexing } from "@/components/retrieval/document-indexing";
import { ApiClientError } from "@/lib/api/client";
import { getProfiles } from "@/lib/api/profiles";
import { indexDocument, searchEvidence } from "@/lib/api/retrieval";
import type { Profile, SourceDocument } from "@/lib/types/api";

vi.mock("@/lib/api/profiles", () => ({ getProfiles: vi.fn() }));
vi.mock("@/lib/api/retrieval", () => ({
  indexDocument: vi.fn(),
  searchEvidence: vi.fn(),
}));

const profile: Profile = {
  id: "profile-a",
  owner_user_id: "owner",
  display_name: "Profile A",
  relationship_to_owner: "SELF",
  date_of_birth: null,
  sex: null,
  access_level: "PRIVATE",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const document: SourceDocument = {
  id: "document-a",
  profile_id: profile.id,
  original_filename: "glucose.txt",
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

beforeEach(() => {
  vi.mocked(getProfiles).mockResolvedValue([profile]);
});

describe("document indexing", () => {
  it("indexes a parsed document and shows the chunk count", async () => {
    vi.mocked(indexDocument).mockResolvedValue({
      document_id: document.id,
      status: "INDEXED",
      chunk_count: 2,
    });
    const refreshed = vi.fn().mockResolvedValue(undefined);
    render(<DocumentIndexing document={document} onIndexed={refreshed} />);

    fireEvent.click(screen.getByRole("button", { name: "Index for Search" }));

    expect(await screen.findByText("Indexed successfully. Chunks: 2")).toBeInTheDocument();
    expect(screen.getByText("Indexed")).toBeInTheDocument();
    expect(refreshed).toHaveBeenCalledOnce();
  });
});

describe("semantic search", () => {
  function renderSearch() {
    return render(<ProfileProvider><SearchPage /></ProfileProvider>);
  }

  it("shows traceable evidence and labels similarity correctly", async () => {
    vi.mocked(searchEvidence).mockResolvedValue({
      query: "glucose",
      indexed_document_count: 1,
      results: [{
        score: 0.82,
        similarity_label: "retrieval similarity",
        document_id: document.id,
        filename: document.original_filename,
        page_number: 1,
        text: "Fasting glucose: 118 mg/dL",
        chunk_index: 0,
      }],
    });
    renderSearch();
    const input = await screen.findByLabelText("Search your uploaded health records...");
    fireEvent.change(input, { target: { value: "glucose" } });
    fireEvent.click(screen.getByRole("button", { name: "Search evidence" }));

    expect(await screen.findByText("Fasting glucose: 118 mg/dL")).toBeInTheDocument();
    expect(screen.getByText("Retrieval similarity 82%")).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();
    expect(screen.getByText(/not medical answers/i)).toBeInTheDocument();
  });

  it("shows indexed and unavailable empty states without fabricating an answer", async () => {
    vi.mocked(searchEvidence).mockResolvedValueOnce({
      query: "glucose",
      indexed_document_count: 0,
      results: [],
    });
    const view = renderSearch();
    let input = await screen.findByLabelText("Search your uploaded health records...");
    fireEvent.change(input, { target: { value: "glucose" } });
    fireEvent.submit(input.closest("form")!);
    expect(await screen.findByText("No documents have been indexed for semantic search.")).toBeInTheDocument();

    view.unmount();
    vi.mocked(searchEvidence).mockRejectedValueOnce(new ApiClientError(
      "Semantic retrieval is currently unavailable.",
      503,
      "VECTOR_STORE_UNAVAILABLE",
    ));
    renderSearch();
    input = await screen.findByLabelText("Search your uploaded health records...");
    fireEvent.change(input, { target: { value: "glucose" } });
    fireEvent.submit(input.closest("form")!);
    expect(await screen.findByText("Semantic retrieval is currently unavailable.")).toBeInTheDocument();
  });
});
