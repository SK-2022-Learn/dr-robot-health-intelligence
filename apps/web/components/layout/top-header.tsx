"use client";

import Link from "next/link";

import { useProfile } from "@/components/health/profile-context";
import { initials } from "@/lib/utils/format";

export function TopHeader() {
  const { profiles, activeProfile, setActiveProfileId, loading, error } = useProfile();
  return (
    <header className="top-header">
      <div className="mobile-brand">DR</div>
      <div className="profile-control">
        <label htmlFor="profile-selector">Viewing profile</label>
        <select
          id="profile-selector"
          value={activeProfile?.id ?? ""}
          onChange={(event) => setActiveProfileId(event.target.value)}
          disabled={loading || profiles.length === 0}
          aria-describedby={error ? "profile-error" : undefined}
        >
          {profiles.length === 0 && <option value="">{loading ? "Loading profiles…" : "No profiles"}</option>}
          {profiles.map((profile) => <option value={profile.id} key={profile.id}>{profile.display_name}</option>)}
        </select>
        {error && <span id="profile-error" className="sr-only">{error}</span>}
      </div>
      <div className="header-actions">
        <Link className="ask-button" href="/chat">Ask Dr. Robot <span>Unified</span></Link>
        <div className="avatar" aria-hidden="true">{activeProfile ? initials(activeProfile.display_name) : "DR"}</div>
      </div>
    </header>
  );
}
