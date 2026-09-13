import Link from "next/link";

import type { EvidenceContext } from "@/lib/types/api";

export function EvidenceCard({ result }: { result: EvidenceContext }) {
  return (
    <article className="evidence-card">
      <p className="eyebrow">Semantic retrieval result</p>
      <div className="evidence-card-head">
        <div>
          <strong>{result.filename}</strong>
          <span>Page {result.page_number}</span>
        </div>
        <span className="similarity">
          Retrieval similarity {Math.round(result.score * 100)}%
        </span>
      </div>
      <blockquote>{result.text}</blockquote>
      <Link className="text-link" href="/uploads">
        Open uploaded document &rarr;
      </Link>
    </article>
  );
}
