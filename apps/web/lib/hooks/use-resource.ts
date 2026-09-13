"use client";

import { useEffect, useState } from "react";

import { readableApiError } from "@/lib/api/client";

type ResourceState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
};

type KeyedResourceState<T> = ResourceState<T> & { key: string | null };

export function useResource<T>(
  loader: (signal?: AbortSignal) => Promise<T>,
  dependency: string | null = "global",
): ResourceState<T> {
  const [state, setState] = useState<KeyedResourceState<T>>({
    data: null,
    error: null,
    loading: true,
    key: null,
  });

  useEffect(() => {
    if (dependency === null) return;
    const controller = new AbortController();
    loader(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ data, error: null, loading: false, key: dependency });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ data: null, error: readableApiError(error), loading: false, key: dependency });
        }
      });
    return () => controller.abort();
  }, [dependency, loader]);

  return state.key === dependency
    ? state
    : { data: null, error: null, loading: true };
}
