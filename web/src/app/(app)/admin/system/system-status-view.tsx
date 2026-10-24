"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, CircleCheck, CircleX, Database, Network, RefreshCw, Server } from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { useUser } from "@/components/auth/user-provider";
import { IconTile, PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";

type Check = { ok: boolean; detail: string };
type Health = { ok: boolean; checks: Record<string, Check> };

const SERVICES: Record<string, { label: string; icon: typeof Server; what: string }> = {
  api: { label: "API", icon: Server, what: "FastAPI backend that serves the portal" },
  db: { label: "Database", icon: Database, what: "Postgres 17 + pgvector: profiles, search index, job orders" },
  langsmith: { label: "LangSmith", icon: Network, what: "Tracing for every AI run" },
};

const HEADER = {
  icon: Activity,
  eyebrow: "Admin",
  title: "System status",
  description: "Live check that every service the portal depends on is connected.",
};

/** Admin-only, like the other admin pages: a skeleton until the user is known, then recruiters get the
 * "Admins only" state without any request being made. */
export function SystemStatusView() {
  const { user, loading } = useUser();
  if (!user && !loading) {   // /api/auth/me finished without a user (e.g. the api restarting); on a 401 this shows briefly before the redirect to /login
    return (
      <div className="space-y-6">
        <PageHeader {...HEADER} />
        <ApiErrorState error={new ApiError(503, "Couldn't load your account. Refresh the page to try again.")} />
      </div>
    );
  }
  if (!user) {
    return (
      <div className="space-y-6">
        <PageHeader {...HEADER} />
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }
  if (user.role !== "admin") {
    return (
      <div className="space-y-6">
        <PageHeader {...HEADER} />
        <ApiErrorState error={new ApiError(403, "Admins only")} />
      </div>
    );
  }
  return <StatusChecks />;
}

function StatusChecks() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // A 503 still returns JSON saying which dependency is down. If the api is unreachable, the Next
      // rewrite returns an HTML 500, so res.json() throws and the catch below shows the message.
      const res = await fetch("/api/health", { cache: "no-store" });
      setHealth((await res.json()) as Health);
    } catch {
      setHealth(null);
      setError("Can't reach the API. Is the api container running?");
    } finally {
      setLoading(false);
      setCheckedAt(new Date());
    }
  }, []);

  useEffect(() => {
    // Fetch once on mount; load() sets the loading flag first, which is intended.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const allOk = health?.ok;
  return (
    <div className="space-y-6">
      <PageHeader
        {...HEADER}
        actions={
          <Button variant="outline" onClick={load} disabled={loading} className="gap-1.5">
            <RefreshCw className={loading ? "animate-spin" : undefined} aria-hidden="true" /> Recheck
          </Button>
        }
      />
      <Card className={allOk === false || error ? "border-danger/40" : undefined}>
        <CardContent className="flex items-center gap-3">
          {allOk ? (
            <CircleCheck className="size-5 text-success" aria-hidden="true" />
          ) : (
            <CircleX className="size-5 text-danger" aria-hidden="true" />
          )}
          <p className="font-medium">
            {loading && !health ? "Checking services…" : error ? error : allOk ? "All systems operational" : "Some services need attention"}
          </p>
          {checkedAt && (
            <p className="ml-auto text-xs text-muted-foreground tabular-nums" suppressHydrationWarning>
              Checked {checkedAt.toLocaleTimeString()}
            </p>
          )}
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-3">
        {loading && !health
          ? Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)
          : Object.entries(health?.checks ?? {}).map(([key, check]) => {
              const s = SERVICES[key] ?? { label: key, icon: Server, what: "" };
              return (
                <Card key={key}>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <IconTile icon={s.icon} />
                        <p className="font-semibold">{s.label}</p>
                      </div>
                      <span
                        className={
                          check.ok
                            ? "rounded-full bg-success-soft px-2.5 py-0.5 text-xs font-medium text-success-strong"
                            : "rounded-full bg-danger-soft px-2.5 py-0.5 text-xs font-medium text-danger-strong"
                        }
                      >
                        {check.ok ? "Connected" : "Down"}
                      </span>
                    </div>
                    {s.what && <p className="text-xs text-muted-foreground">{s.what}</p>}
                    <p className="text-sm">{check.detail}</p>
                  </CardContent>
                </Card>
              );
            })}
      </div>
    </div>
  );
}
