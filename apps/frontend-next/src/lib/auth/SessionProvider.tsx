"use client";

import { createContext, useCallback, useContext, useMemo, useSyncExternalStore, type ReactNode } from "react";
import { authApi, type Role } from "@/lib/api";
import { clearSession, loadSession, saveSession, type Session } from "./session";

interface SessionContextValue {
  session: Session | null;
  ready: boolean;
  signIn: (username: string, role: Role) => Promise<Session>;
  signOut: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

type Snapshot = { session: Session | null } | null;

let snapshot: Snapshot = null;
const listeners = new Set<() => void>();

function setSnapshot(session: Session | null) {
  snapshot = { session };
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): Snapshot {
  if (snapshot === null) {
    snapshot = { session: loadSession() };
  }
  return snapshot;
}

function getServerSnapshot(): Snapshot {
  return null;
}

export function resetSessionStoreForTests() {
  snapshot = null;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const current = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const signIn = useCallback(async (username: string, role: Role) => {
    const issued = await authApi.devToken({ username, role });
    const session: Session = { token: issued.token, expiresAt: issued.expiresAt, username, role };
    saveSession(session);
    setSnapshot(session);
    return session;
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setSnapshot(null);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({ session: current?.session ?? null, ready: current !== null, signIn, signOut }),
    [current, signIn, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSession must be used inside SessionProvider");
  }
  return value;
}
