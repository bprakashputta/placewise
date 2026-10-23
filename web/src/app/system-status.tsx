"use client";

import { useCallback, useEffect, useState } from "react";

type Check = { ok: boolean; detail: string };
type Health = { ok: boolean; checks: Record<string, Check> };

const LABELS: Record<string, string> = { api: "API", db: "Database", langsmith: "LangSmith" };

export function SystemStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 503 still returns a JSON body describing which dependency is down.
      const res = await fetch("/api/health", { cache: "no-store" });
      setHealth((await res.json()) as Health);
    } catch {
      setHealth(null);
      setError("Can't reach the API. Is the api container running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch once on mount; load() sets the loading flag before the request, which is intended.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  return (
    <section className="rounded-xl border border-neutral-200 bg-white shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
        {loading && !health && <li className="px-5 py-4 text-sm text-neutral-500">Checking services…</li>}
        {error && <li className="px-5 py-4 text-sm text-red-600 dark:text-red-400">{error}</li>}
        {health &&
          Object.entries(health.checks).map(([key, check]) => (
            <li key={key} className="flex items-start justify-between gap-4 px-5 py-4">
              <div>
                <p className="font-medium">{LABELS[key] ?? key}</p>
                <p className="text-sm text-neutral-500 dark:text-neutral-400">{check.detail}</p>
              </div>
              <span
                className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
                  check.ok
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                    : "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
                }`}
              >
                {check.ok ? "✓ Connected" : "✕ Down"}
              </span>
            </li>
          ))}
      </ul>
      <div className="flex items-center justify-between border-t border-neutral-200 px-5 py-3 dark:border-neutral-800">
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          {health ? (health.ok ? "All systems operational" : "Some services need attention") : " "}
        </p>
        <button
          onClick={load}
          disabled={loading}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          {loading ? "Checking…" : "Recheck"}
        </button>
      </div>
    </section>
  );
}
