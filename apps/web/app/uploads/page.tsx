"use client";

import { useCallback, useEffect, useState } from "react";

import { useProfile } from "@/components/health/profile-context";
import { CandidateReview } from "@/components/extraction/candidate-review";
import { Card, EmptyState, ErrorState, LoadingState, PageHeading, StatusPill } from "@/components/ui";
import { ApiClientError, readableApiError } from "@/lib/api/client";
import {
  ACCEPTED_DOCUMENT_TYPES,
  getDocument,
  getDocumentPages,
  getDocuments,
  MAX_UPLOAD_SIZE_MB,
  uploadDocument,
} from "@/lib/api/documents";
import { useResource } from "@/lib/hooks/use-resource";
import type { DocumentPage, Profile, SourceDocument } from "@/lib/types/api";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

type UploadState = "ready" | "uploading" | "processing" | "parsed" | "needs_ocr" | "failed" | "duplicate";

const uploadLabels: Record<UploadState, string> = {
  ready: "Ready",
  uploading: "Uploading",
  processing: "Processing",
  parsed: "Parsed",
  needs_ocr: "Needs OCR",
  failed: "Failed",
  duplicate: "Duplicate",
};

const allowedExtensions = new Set(["pdf", "txt", "png", "jpg", "jpeg"]);

function validateSelectedFile(file: File): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!allowedExtensions.has(extension)) return "Choose a PDF, TXT, PNG, JPG, or JPEG file.";
  if (file.size === 0) return "The selected file is empty.";
  if (file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) return `Files must be ${MAX_UPLOAD_SIZE_MB} MB or smaller.`;
  return null;
}

function UploadsForProfile({ profile }: { profile: Profile }) {
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentDate, setDocumentDate] = useState("");
  const [uploadState, setUploadState] = useState<UploadState>("ready");
  const [message, setMessage] = useState("Choose a document to begin.");
  const [dragging, setDragging] = useState(false);
  const [detail, setDetail] = useState<SourceDocument | null>(null);
  const [pages, setPages] = useState<DocumentPage[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const sourceQuery = typeof window === "undefined" ? null : new URLSearchParams(window.location.search);
  const requestedDocumentId = sourceQuery?.get("document") ?? null;
  const requestedPage = Number(sourceQuery?.get("page") ?? "") || null;

  const loader = useCallback(
    (signal?: AbortSignal) => getDocuments(profile.id, signal),
    [profile.id],
  );
  const documents = useResource(loader, `${profile.id}:${refreshVersion}`);

  function chooseFile(file: File | null) {
    setSelectedFile(file);
    if (!file) {
      setUploadState("ready");
      setMessage("Choose a document to begin.");
      return;
    }
    const issue = validateSelectedFile(file);
    setUploadState(issue ? "failed" : "ready");
    setMessage(issue ?? `${file.name} is ready to upload.`);
  }

  const openDocument = useCallback(async (document: SourceDocument) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const [metadata, extractedPages] = await Promise.all([
        getDocument(document.id),
        getDocumentPages(document.id),
      ]);
      setDetail(metadata);
      setPages(extractedPages);
    } catch (reason: unknown) {
      setDetailError(readableApiError(reason));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!requestedDocumentId || !documents.data || detail?.id === requestedDocumentId) return;
    const requested = documents.data.find((document) => document.id === requestedDocumentId);
    if (!requested) return;
    const controller = new AbortController();
    Promise.all([
      getDocument(requested.id, controller.signal),
      getDocumentPages(requested.id, controller.signal),
    ])
      .then(([metadata, extractedPages]) => {
        setDetail(metadata);
        setPages(extractedPages);
        setDetailError(null);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setDetailError(readableApiError(reason));
      });
    return () => controller.abort();
  }, [detail?.id, documents.data, requestedDocumentId]);

  useEffect(() => {
    if (!detail || !requestedPage) return;
    document.getElementById(`document-page-${requestedPage}`)?.scrollIntoView({ block: "center" });
  }, [detail, requestedPage]);

  async function submitUpload() {
    if (!selectedFile) {
      setUploadState("failed");
      setMessage("Choose a file before uploading.");
      return;
    }
    const issue = validateSelectedFile(selectedFile);
    if (issue) {
      setUploadState("failed");
      setMessage(issue);
      return;
    }
    setUploadState("uploading");
    setMessage(`Securely uploading ${selectedFile.name}…`);
    try {
      const uploaded = await uploadDocument(profile.id, selectedFile, documentDate, () => {
        setUploadState("processing");
        setMessage("Upload complete. Extracting raw text when supported…");
      });
      setUploadState(uploaded.status === "NEEDS_OCR" ? "needs_ocr" : uploaded.status === "FAILED" ? "failed" : "parsed");
      setMessage(
        uploaded.status === "PARSED"
          ? "Raw document text was parsed successfully."
          : uploaded.status === "NEEDS_OCR"
            ? "The file is stored safely and needs OCR before text can be extracted."
            : "The file is stored, but parsing failed. It can be retried in a future phase.",
      );
      setRefreshVersion((current) => current + 1);
      await openDocument(uploaded);
    } catch (reason: unknown) {
      const duplicate = reason instanceof ApiClientError && reason.code === "DUPLICATE_DOCUMENT";
      setUploadState(duplicate ? "duplicate" : "failed");
      setMessage(readableApiError(reason));
    }
  }

  return <>
    <PageHeading eyebrow="Source records" title="Upload Records" description={`Securely store and parse source documents for ${profile.display_name}. Parsing never creates verified health facts.`} />
    <Card className={dragging ? "upload-panel dragging" : "upload-panel"}>
      <div className="upload-icon">↑</div>
      <div
        className="drop-target"
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0] ?? null); }}
      >
        <h2>Drag and drop a document here</h2>
        <p>PDF, TXT, PNG, JPG, or JPEG · Maximum {MAX_UPLOAD_SIZE_MB} MB</p>
        <strong>{selectedFile?.name ?? "No file selected"}</strong>
      </div>
      <div className="upload-actions">
        <label className="browse-button" htmlFor="document-file">Browse Files</label>
        <input id="document-file" className="sr-only" type="file" accept={ACCEPTED_DOCUMENT_TYPES} onChange={(event) => chooseFile(event.target.files?.[0] ?? null)} />
        <label htmlFor="document-date">Document date <span>optional</span></label>
        <input id="document-date" type="date" value={documentDate} onChange={(event) => setDocumentDate(event.target.value)} />
        <button className="primary-button" onClick={submitUpload} disabled={!selectedFile || uploadState === "uploading" || uploadState === "processing"}>Upload document</button>
      </div>
    </Card>

    <div className={`upload-result result-${uploadState}`} role="status"><span className={uploadState === "uploading" || uploadState === "processing" ? "spinner" : "result-dot"} /><div><strong>{uploadLabels[uploadState]}</strong><p>{message}</p></div></div>

    <Card title="Processing stages" className="processing-card"><div className="processing-stages"><span>1. Validate</span><span>2. Secure storage</span><span>3. Raw parsing / OCR</span><span>4. Save page text</span></div><p className="helper-text">No health facts or timeline events are created by this process.</p></Card>

    <Card title="Recent Documents">{documents.loading ? <LoadingState label="Loading document records…" /> : documents.error ? <ErrorState message={documents.error} /> : !documents.data?.length ? <EmptyState title="No documents stored" message="Upload a supported synthetic document to begin." /> : <div className="document-list">{documents.data.map((document) => <button className="document-row" key={document.id} onClick={() => openDocument(document)}><div><strong>{document.original_filename}</strong><span>{document.mime_type} · {formatDate(document.document_date ?? document.created_at)}</span></div><span>{document.page_count} page{document.page_count === 1 ? "" : "s"}</span><StatusPill tone={document.status === "PARSED" ? "good" : "warm"}>{friendlyLabel(document.status)}</StatusPill></button>)}</div>}</Card>

    {(detailLoading || detail || detailError) && <Card title="Document detail" className="document-detail">{detailLoading ? <LoadingState label="Loading document details…" /> : detailError ? <ErrorState message={detailError} /> : detail && <><div className="detail-grid"><div><span>Original filename</span><strong>{detail.original_filename}</strong></div><div><span>Upload date</span><strong>{formatDate(detail.created_at)}</strong></div><div><span>Status</span><StatusPill tone={detail.status === "PARSED" ? "good" : "warm"}>{friendlyLabel(detail.status)}</StatusPill></div><div><span>MIME type</span><strong>{detail.mime_type}</strong></div><div><span>Page count</span><strong>{detail.page_count}</strong></div><div><span>Extraction</span><strong>{detail.has_extracted_text ? "Raw text available" : "No text extracted"}</strong></div></div><div className="extraction-warning">Extracted document text has not yet been converted into verified health facts.</div><h3>RAW EXTRACTED TEXT</h3>{pages.some((page) => page.text.trim()) ? <div className="raw-pages">{pages.map((page) => <section id={`document-page-${page.page_number}`} className={requestedPage === page.page_number ? "source-page-highlight" : ""} key={page.id}><strong>Page {page.page_number}</strong><pre>{page.text || "No extractable text on this page."}</pre></section>)}</div> : <EmptyState title={detail.status === "NEEDS_OCR" ? "OCR required" : "No extracted text"} message="The original file remains stored safely. No text was fabricated." />}<CandidateReview key={detail.id} document={detail} /></>}</Card>}
  </>;
}

export default function UploadsPage() {
  const { activeProfile, loading, error } = useProfile();
  if (loading) return <LoadingState label="Loading profile…" />;
  if (error) return <ErrorState message={error} />;
  if (!activeProfile) return <EmptyState title="No profile selected" message="Choose a health profile before uploading documents." />;
  return <UploadsForProfile key={activeProfile.id} profile={activeProfile} />;
}
