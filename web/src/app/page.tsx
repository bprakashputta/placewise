import Link from "next/link";
import { SystemStatus } from "./system-status";

// Block 0 placeholder: proves browser → web → api → db (and LangSmith) all connect.
// The real portal (login, dashboard, job orders) replaces this page in Block 3.
export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center gap-8 px-6 py-16">
      <header className="space-y-2">
        <p className="text-sm font-medium tracking-wide text-indigo-600 dark:text-indigo-400">PLACEWISE</p>
        <h1 className="text-3xl font-semibold tracking-tight">System status</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          AI layer for A/E/C recruiting. This page checks that every service is connected.
        </p>
      </header>
      <SystemStatus />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <a href="/admin/test-data" className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400">
          View synthetic seed data (dev) →
        </a>
        <Link href="/dashboard" className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400">
          Open portal →
        </Link>
      </div>
    </main>
  );
}
