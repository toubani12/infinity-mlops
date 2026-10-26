"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ApiError, type Role } from "@/lib/api";
import { useSession } from "@/lib/auth";

export function LoginForm() {
  const { signIn } = useSession();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<Role>("analyst");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await signIn(username.trim(), role);
      router.replace("/transactions");
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 404
          ? "Dev sign-in is off. Start the backend with the local profile."
          : e instanceof ApiError
            ? e.message
            : "The backend did not answer. Check that it runs on the configured API URL.",
      );
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5" noValidate>
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        Username
        <input
          name="username"
          required
          maxLength={64}
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="rounded-md border border-line bg-surface px-3 py-2 text-[15px] font-normal"
        />
      </label>
      <fieldset className="flex flex-col gap-2 text-sm">
        <legend className="mb-1.5 font-medium">Role</legend>
        {(["analyst", "admin"] as const).map((value) => (
          <label key={value} className="flex items-start gap-2.5">
            <input
              type="radio"
              name="role"
              value={value}
              checked={role === value}
              onChange={() => setRole(value)}
              className="mt-1 accent-accent"
            />
            <span>
              <span className="font-medium capitalize">{value}</span>
              <span className="block text-muted">
                {value === "analyst" ? "Review transactions and alerts." : "Everything an analyst does, plus approving promotions."}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      {error ? (
        <p role="alert" className="rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={submitting || username.trim() === ""}
        className="rounded-md bg-accent px-4 py-2.5 text-[15px] font-semibold text-white disabled:opacity-50"
      >
        {submitting ? "Signing in" : "Sign in"}
      </button>
    </form>
  );
}
