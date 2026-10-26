import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { SessionProvider } from "@/lib/auth";
import { resetSessionStoreForTests } from "@/lib/auth/SessionProvider";
import { saveSession, type Session } from "@/lib/auth/session";
import { session } from "./fixtures";

export function renderWithSession(ui: ReactNode, signedIn: boolean | Partial<Session> = true) {
  resetSessionStoreForTests();
  window.sessionStorage.clear();
  if (signedIn) {
    saveSession(session(signedIn === true ? {} : signedIn));
  }
  return render(<SessionProvider>{ui}</SessionProvider>);
}
