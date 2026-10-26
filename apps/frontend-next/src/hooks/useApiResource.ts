"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { ApiError } from "@/lib/api";
import { useSession } from "@/lib/auth";

export type Resource<T> =
  | { state: "loading" }
  | { state: "ready"; data: T }
  | { state: "error"; status: number | null; message: string };

/** Loads one API resource with the session token; a 401 ends the session so the guard sends the user to sign in. */
export function useApiResource<T>(
  key: string,
  load: (token: string, signal: AbortSignal) => Promise<T>,
): Resource<T> {
  const { session, signOut } = useSession();
  const token = session?.token ?? null;
  const [result, setResult] = useState<{ key: string; resource: Resource<T> } | null>(null);
  const run = useEffectEvent(load);

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    run(token, controller.signal)
      .then((data) => setResult({ key, resource: { state: "ready", data } }))
      .catch((e: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (e instanceof ApiError && e.status === 401) {
          signOut();
          return;
        }
        const status = e instanceof ApiError ? e.status : null;
        const message = e instanceof Error ? e.message : "The request failed.";
        setResult({ key, resource: { state: "error", status, message } });
      });
    return () => controller.abort();
  }, [key, token, signOut]);

  return result && result.key === key ? result.resource : { state: "loading" };
}
