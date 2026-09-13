import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UploadsPage from "@/app/uploads/page";
import { ProfileProvider } from "@/components/health/profile-context";
import { ApiClientError } from "@/lib/api/client";
import { getDocument, getDocumentPages, getDocuments, uploadDocument } from "@/lib/api/documents";
import { getCandidates } from "@/lib/api/extraction";
import { getProfiles } from "@/lib/api/profiles";
import type { DocumentPage, Profile, SourceDocument } from "@/lib/types/api";

vi.mock("@/lib/api/profiles", () => ({ getProfiles: vi.fn() }));
vi.mock("@/lib/api/extraction", () => ({
  acceptCandidate: vi.fn(),
  correctCandidate: vi.fn(),
  extractDocument: vi.fn(),
  getCandidates: vi.fn(),
  rejectCandidate: vi.fn(),
}));
vi.mock("@/lib/api/documents", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/documents")>();
  return {
    ...original,
    getDocuments: vi.fn(),
    getDocument: vi.fn(),
    getDocumentPages: vi.fn(),
    uploadDocument: vi.fn(),
  };
});

const profile: Profile = {
  id: "profile-upload",
  owner_user_id: "owner",
  display_name: "Synthetic Person",
  relationship_to_owner: "SELF",
  date_of_birth: null,
  sex: null,
  access_level: "PRIVATE",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const parsedDocument: SourceDocument = {
  id: "document-1",
  profile_id: profile.id,
  original_filename: "synthetic.txt",
  mime_type: "text/plain",
  document_date: null,
  status: "PARSED",
  page_count: 1,
  has_extracted_text: true,
  vector_index_status: "NOT_INDEXED",
  vector_indexed_at: null,
  vector_chunk_count: 0,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

const page: DocumentPage = {
  id: "page-1",
  document_id: parsedDocument.id,
  page_number: 1,
  text: "Synthetic raw text only.",
  created_at: "2026-01-02T00:00:00Z",
};

function renderUploads() {
  return render(<ProfileProvider><UploadsPage /></ProfileProvider>);
}

function selectFile(name = "synthetic.txt", content = "Synthetic text", type = "text/plain") {
  const input = screen.getByLabelText("Browse Files");
  const file = new File([content], name, { type });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

beforeEach(() => {
  vi.mocked(getProfiles).mockResolvedValue([profile]);
  vi.mocked(getDocuments).mockResolvedValue([]);
  vi.mocked(getDocument).mockResolvedValue(parsedDocument);
  vi.mocked(getDocumentPages).mockResolvedValue([page]);
  vi.mocked(uploadDocument).mockImplementation(async (_profileId, _file, _date, complete) => {
    complete?.();
    return parsedDocument;
  });
  vi.mocked(getCandidates).mockResolvedValue([]);
});

describe("Uploads screen", () => {
  it("renders the functional upload controls and limits", async () => {
    renderUploads();
    expect(await screen.findByRole("heading", { name: "Upload Records" })).toBeInTheDocument();
    expect(screen.getByText(/Maximum 15 MB/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload document" })).toBeDisabled();
  });

  it("accepts a supported file selection", async () => {
    renderUploads();
    await screen.findByRole("heading", { name: "Upload Records" });
    selectFile();
    expect(screen.getByText("synthetic.txt is ready to upload.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload document" })).toBeEnabled();
  });

  it("shows an unsupported-file state before upload", async () => {
    renderUploads();
    await screen.findByRole("heading", { name: "Upload Records" });
    selectFile("unsafe.exe", "binary", "application/octet-stream");
    expect(screen.getByText("Choose a PDF, TXT, PNG, JPG, or JPEG file.")).toBeInTheDocument();
  });

  it("uploads, refreshes recent documents, and opens raw page text", async () => {
    renderUploads();
    await screen.findByRole("heading", { name: "Upload Records" });
    selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByText("Raw document text was parsed successfully.")).toBeInTheDocument();
    expect(await screen.findByText("Synthetic raw text only.")).toBeInTheDocument();
    expect(screen.getByText("RAW EXTRACTED TEXT")).toBeInTheDocument();
    expect(screen.getByText(/has not yet been converted into verified health facts/)).toBeInTheDocument();
    await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(2));
  });

  it("shows backend upload failures", async () => {
    vi.mocked(uploadDocument).mockRejectedValue(new ApiClientError("Upload rejected.", 415, "UNSUPPORTED_FILE_TYPE"));
    renderUploads();
    await screen.findByRole("heading", { name: "Upload Records" });
    selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByText("Upload rejected.")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows duplicate and Needs OCR states", async () => {
    vi.mocked(uploadDocument).mockRejectedValueOnce(new ApiClientError("Already stored.", 409, "DUPLICATE_DOCUMENT"));
    const needsOcr = { ...parsedDocument, id: "image-1", original_filename: "scan.png", mime_type: "image/png", status: "NEEDS_OCR" as const, has_extracted_text: false };
    vi.mocked(uploadDocument).mockResolvedValueOnce(needsOcr);
    vi.mocked(getDocument).mockResolvedValue(needsOcr);
    vi.mocked(getDocumentPages).mockResolvedValue([]);
    renderUploads();
    await screen.findByRole("heading", { name: "Upload Records" });
    selectFile();
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByText("Already stored.")).toBeInTheDocument();
    selectFile("scan.png", "synthetic image bytes", "image/png");
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(await screen.findByText(/needs OCR before text can be extracted/)).toBeInTheDocument();
    expect(screen.getByText("OCR required")).toBeInTheDocument();
  });

  it("opens an existing recent document detail", async () => {
    vi.mocked(getDocuments).mockResolvedValue([parsedDocument]);
    renderUploads();
    const documentButton = await screen.findByRole("button", { name: /synthetic\.txt/ });
    fireEvent.click(documentButton);
    expect(await screen.findByText("Raw text available")).toBeInTheDocument();
    expect(getDocument).toHaveBeenCalledWith(parsedDocument.id);
    expect(getDocumentPages).toHaveBeenCalledWith(parsedDocument.id);
  });
});
