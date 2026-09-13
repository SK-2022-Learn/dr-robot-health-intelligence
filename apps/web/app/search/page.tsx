"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { useProfile } from "@/components/health/profile-context";
import { EvidenceCard } from "@/components/retrieval/evidence-card";
import { Card, EmptyState, ErrorState, LoadingState, PageHeading } from "@/components/ui";
import { readableApiError } from "@/lib/api/client";
import { searchEvidence } from "@/lib/api/retrieval";
import type { RetrievalSearchResponse } from "@/lib/types/api";

export default function SearchPage() {
  const { activeProfile, loading, error: profileError } = useProfile();
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [response, setResponse] = useState<RetrievalSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProfile || !query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      setResponse(await searchEvidence(activeProfile.id, query.trim()));
    } catch (reason: unknown) {
      setResponse(null);
      setError(readableApiError(reason));
    } finally {
      setSearching(false);
    }
  }

  if (loading) return <LoadingState label="Loading profile..." />;
  if (profileError) return <ErrorState message={profileError} />;
  if (!activeProfile) {
    return <EmptyState title="No profile selected" message="Choose a profile before searching records." />;
  }

  return (
    <>
      <PageHeading
        eyebrow="Source evidence"
        title="Semantic Search"
        description={`Search indexed document passages for ${activeProfile.display_name}. Results are evidence excerpts, not medical answers.`}
      />
      <Card className="search-panel">
        <form onSubmit={submit} className="search-form">
          <label htmlFor="semantic-query">Search your uploaded health records...</label>
          <div>
            <input
              id="semantic-query"
              value={query}
              maxLength={500}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="What do my records say about glucose?"
            />
            <button className="primary-button" disabled={searching || !query.trim()}>
              {searching ? "Searching..." : "Search evidence"}
            </button>
          </div>
        </form>
        <p className="helper-text">
          Search is restricted to the currently selected profile. Retrieval similarity is not medical confidence.
        </p>
      </Card>
      {error && <ErrorState message={error} />}
      {response && response.indexed_document_count === 0 && (
        <Card>
          <EmptyState
            title="No documents indexed"
            message="No documents have been indexed for semantic search."
          />
          <Link className="text-link" href="/uploads">
            Go to Uploads to index a document &rarr;
          </Link>
        </Card>
      )}
      {response && response.indexed_document_count > 0 && response.results.length === 0 && (
        <Card>
          <EmptyState
            title="No relevant evidence"
            message="No relevant evidence was found in the indexed records."
          />
        </Card>
      )}
      {response && response.results.length > 0 && (
        <section className="evidence-results" aria-label="Semantic retrieval results">
          {response.results.map((result) => (
            <EvidenceCard
              key={`${result.document_id}:${result.page_number}:${result.chunk_index}`}
              result={result}
            />
          ))}
        </section>
      )}
    </>
  );
}
