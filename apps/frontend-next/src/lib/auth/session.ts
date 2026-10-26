import type { Role } from "@/lib/api";

export interface Session {
  token: string;
  expiresAt: string;
  username: string;
  role: Role;
}

const STORAGE_KEY = "infinity.session";
const SIGN_OUT_KEY = "infinity.signout";

export type SignOutReason = "expired";

export function isExpired(session: Session, now: number = Date.now()): boolean {
  return Date.parse(session.expiresAt) <= now;
}

export function loadSession(now: number = Date.now()): Session | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const session = JSON.parse(raw) as Session;
    if (!session.token || isExpired(session, now)) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function saveSession(session: Session): void {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Storage can be blocked (private mode); the in-memory session still works for this tab.
  }
}

export function saveSignOutReason(reason: SignOutReason | null): void {
  try {
    if (reason) {
      window.sessionStorage.setItem(SIGN_OUT_KEY, reason);
    } else {
      window.sessionStorage.removeItem(SIGN_OUT_KEY);
    }
  } catch {
    // Without storage the login page simply shows no notice.
  }
}

export function loadSignOutReason(): SignOutReason | null {
  try {
    return window.sessionStorage.getItem(SIGN_OUT_KEY) === "expired" ? "expired" : null;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Same as above: nothing to clear when storage is unavailable.
  }
}
