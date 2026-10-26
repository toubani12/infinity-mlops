"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useSession } from "@/lib/auth";

export function RequireSession({ children }: { children: ReactNode }) {
  const { session, ready } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (ready && !session) {
      router.replace("/login");
    }
  }, [ready, session, router]);

  if (!session) {
    return <p className="mt-10 text-sm text-muted">Checking your session.</p>;
  }
  return children;
}
