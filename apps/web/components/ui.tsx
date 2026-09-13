import type { ReactNode } from "react";

export function PageHeading({ eyebrow, title, description }: { eyebrow?: string; title: string; description: string }) {
  return <div className="page-heading">{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1><p>{description}</p></div>;
}

export function Card({ title, action, children, className = "" }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{(title || action) && <div className="card-head">{title && <h2>{title}</h2>}{action}</div>}{children}</section>;
}

export function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warm" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export function LoadingState({ label = "Loading health information…" }: { label?: string }) {
  return <div className="state-panel" role="status"><span className="spinner" />{label}</div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="state-panel error" role="alert"><strong>Unable to load this view</strong><span>{message}</span></div>;
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return <div className="empty-state"><span aria-hidden="true">○</span><strong>{title}</strong><p>{message}</p></div>;
}

export function Disclaimer() {
  return <p className="disclaimer">Dr. Robot organizes stored health information. It does not diagnose, prescribe treatment, or replace professional medical care.</p>;
}
