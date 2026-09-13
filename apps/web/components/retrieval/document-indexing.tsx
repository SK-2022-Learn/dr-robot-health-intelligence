"use client";

import { useState } from "react";

import { ErrorState, StatusPill } from "@/components/ui";
import { readableApiError } from "@/lib/api/client";
import { indexDocument } from "@/lib/api/retrieval";
import type { SourceDocument, VectorIndexStatus } from "@/lib/types/api";
import { friendlyLabel } from "@/lib/utils/format";

export function DocumentIndexing({
  document,
  onIndexed,
}: {
  document: SourceDocument;
  onIndexed: () => Promise<void>;
}) {
  const [status, setStatus] = useState<VectorIndexStatus>(document.vector_index_status);
  const [chunkCount, setChunkCount] = useState(document.vector_chunk_count);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function indexForSearch() {
    setStatus("INDEXING");
    setMessage(null);
    setError(null);
    try {
      const result = await indexDocument(document.id);
      setStatus(result.status);
      setChunkCount(result.chunk_count);
      setMessage(`Indexed successfully. Chunks: ${result.chunk_count}`);
      await onIndexed();
    } catch (reason: unknown) {
      setStatus("INDEX_FAILED");
      setError(readableApiError(reason));
    }
  }

  return (
    <section className="indexing-panel">
      <div>
        <p className="eyebrow">Semantic evidence retrieval</p>
        <h3>Vector indexing</h3>
        <p>Creates profile-isolated search vectors from this document&apos;s parsed pages.</p>
      </div>
      <div className="indexing-status">
        <span>Vector indexing status</span>
        <StatusPill
          tone={status === "INDEXED" ? "good" : status === "INDEX_FAILED" ? "warm" : "neutral"}
        >
          {friendlyLabel(status)}
        </StatusPill>
        {chunkCount > 0 && (
          <strong>
            {chunkCount} chunk{chunkCount === 1 ? "" : "s"}
          </strong>
        )}
      </div>
      <button
        className="primary-button"
        onClick={indexForSearch}
        disabled={document.status !== "PARSED" || status === "INDEXING"}
      >
        {status === "INDEXING"
          ? "Indexing..."
          : status === "INDEXED"
            ? "Reindex for Search"
            : "Index for Search"}
      </button>
      {message && (
        <div className="extraction-notice" role="status">
          {message}
        </div>
      )}
      {error && <ErrorState message={error} />}
    </section>
  );
}
