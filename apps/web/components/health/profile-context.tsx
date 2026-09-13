"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { readableApiError } from "@/lib/api/client";
import { getProfiles } from "@/lib/api/profiles";
import type { Profile } from "@/lib/types/api";

type ProfileContextValue = {
  profiles: Profile[];
  activeProfile: Profile | null;
  setActiveProfileId: (profileId: string) => void;
  loading: boolean;
  error: string | null;
};

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getProfiles(controller.signal)
      .then((result) => {
        setProfiles(result);
        const mainProfile = result.find((profile) => profile.relationship_to_owner === "SELF");
        setActiveProfileId((current) => current ?? mainProfile?.id ?? result[0]?.id ?? null);
        setError(null);
      })
      .catch((reason: unknown) => setError(readableApiError(reason)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const activeProfile = profiles.find((profile) => profile.id === activeProfileId) ?? null;
  const value = useMemo(
    () => ({ profiles, activeProfile, setActiveProfileId, loading, error }),
    [profiles, activeProfile, loading, error],
  );

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

export function useProfile(): ProfileContextValue {
  const context = useContext(ProfileContext);
  if (!context) throw new Error("useProfile must be used inside ProfileProvider.");
  return context;
}
