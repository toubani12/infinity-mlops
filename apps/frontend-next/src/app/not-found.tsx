import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <main className="max-w-md">
        <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
        <p className="mt-2 text-[15px] text-muted">This address does not match any page of the dashboard.</p>
        <Link href="/transactions" className="mt-5 inline-block text-sm font-medium text-accent hover:underline">
          Go to transactions
        </Link>
      </main>
    </div>
  );
}
