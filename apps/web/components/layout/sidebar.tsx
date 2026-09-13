"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  ["/chat", "Ask Dr. Robot", "DR"],
  ["/", "Home", "⌂"],
  ["/my-health", "My Health", "♥"],
  ["/family", "Family", "♧"],
  ["/uploads", "Uploads", "↑"],
  ["/search", "Search", "⌕"],
  ["/timeline", "Timeline", "◷"],
  ["/insights", "Insights", "✦"],
  ["/doctor-visit", "Doctor Visit", "+"],
  ["/settings", "Settings", "⚙"],
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand">
        <span className="brand-logo" aria-hidden="true">+</span>
        <span><strong>Dr. Robot</strong><small>Health intelligence</small></span>
      </div>
      <nav className="nav-list">
        {navigation.map(([href, label, icon]) => {
          const active = href === "/" ? pathname === href : pathname.startsWith(href);
          return (
            <Link key={href} href={href} className={active ? "nav-link active" : "nav-link"} aria-current={active ? "page" : undefined}>
              <span className="nav-icon" aria-hidden="true">{icon}</span>{label}
            </Link>
          );
        })}
      </nav>
      <div className="privacy-note"><span>●</span><p><strong>Private by design</strong><br />Your health story stays traceable to its source.</p></div>
    </aside>
  );
}
