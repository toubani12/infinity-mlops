import type { Metadata } from "next";
import { LoginForm } from "@/components/LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-rail px-4">
      <main className="w-full max-w-sm rounded-lg bg-paper p-7">
        <h1 className="text-2xl font-semibold tracking-tight">Sign in to Infinity</h1>
        <p className="mt-1 mb-6 text-[15px] text-muted">
          Development sign-in: pick a name and a role, the backend issues a token for this browser tab.
        </p>
        <LoginForm />
      </main>
    </div>
  );
}
