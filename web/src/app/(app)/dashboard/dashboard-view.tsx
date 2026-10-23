"use client";

import Link from "next/link";
import { BriefcaseBusiness, CircleAlert, CircleDollarSign, FileCheck2, ListChecks, Users } from "lucide-react";
import { useUser } from "@/components/auth/user-provider";
import { PageHeader } from "@/components/page-header";
import { qualityStyle } from "@/components/quality-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi, type Stats } from "@/lib/api";
import type { JobOrderRow } from "@/lib/job-types";
import { formatNumber, formatUsd, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

const QUALITY_ORDER = ["polished", "flawed", "adversarial", "unusable"];
const QUALITY_HELP: Record<string, string> = {
  polished: "Clean, well-structured resumes",
  flawed: "Readable, with writing or formatting problems",
  adversarial: "Hidden instructions aimed at AI, removed before extraction",
  unusable: "Scanned or corrupt files that need a person",
};

function StatCard({
  label,
  value,
  caption,
  icon: Icon,
  loading,
  href,
  children,
}: {
  label: string;
  value: string;
  caption: React.ReactNode;
  icon: typeof Users;
  loading: boolean;
  href?: string;
  children?: React.ReactNode;
}) {
  const body = (
    <Card className={cn("h-full gap-2", href && "transition-colors hover:border-foreground/20")}>
      <CardHeader>
        <CardDescription className="flex items-center justify-between gap-2">
          <span>{label}</span>
          <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
        </CardDescription>
        <CardTitle className="text-3xl font-semibold tabular-nums">
          {loading ? <Skeleton className="h-9 w-20" /> : value}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {children}
        <p className="text-xs text-muted-foreground">{caption}</p>
      </CardContent>
    </Card>
  );
  return href ? (
    <Link href={href} className="rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
      {body}
    </Link>
  ) : (
    body
  );
}

function QualityBreakdown({ byQuality, loading }: { byQuality?: Record<string, number>; loading: boolean }) {
  const entries = byQuality
    ? [...QUALITY_ORDER.filter((q) => q in byQuality), ...Object.keys(byQuality).filter((q) => !QUALITY_ORDER.includes(q))]
        .map((q) => [q, byQuality[q]] as const)
    : [];
  const total = entries.reduce((s, [, n]) => s + n, 0);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Resume quality</CardTitle>
        <CardDescription>How every processed file was classified before extraction.</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-8" />
            ))}
          </div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">–</p>
        ) : (
          <>
            {/* Stacked overview bar: 2px surface gaps between segments. */}
            <div className="mb-5 flex h-2.5 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
              {entries.map(([q, n]) => (
                <div key={q} className={cn("h-full first:rounded-l-full last:rounded-r-full", qualityStyle(q).bar)} style={{ width: `${(n / Math.max(total, 1)) * 100}%` }} />
              ))}
            </div>
            <ul className="space-y-3">
              {entries.map(([q, n]) => (
                <li key={q} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className={cn("size-2 shrink-0 rounded-full", qualityStyle(q).dot)} aria-hidden="true" />
                    <span className="text-sm font-medium">{humanize(q)}</span>
                    <span className="hidden truncate text-xs text-muted-foreground sm:inline">{QUALITY_HELP[q]}</span>
                  </div>
                  <span className="text-sm tabular-nums">
                    {formatNumber(n)}{" "}
                    <span className="text-muted-foreground">({total ? ((n / total) * 100).toFixed(1) : 0}%)</span>
                  </span>
                  <div className="col-span-2 h-1.5 rounded-full bg-muted" aria-hidden="true">
                    <div className={cn("h-full rounded-full", qualityStyle(q).bar)} style={{ width: `${(n / max) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function DashboardView({ children }: { children: React.ReactNode }) {
  const { user } = useUser();
  const { data: stats, loading, error } = useApi<Stats>("/api/stats");
  const s = error ? undefined : stats;
  // Until /api/stats has job-order fields, derive them from the job-order list.
  const jobs = useApi<JobOrderRow[]>("/api/job-orders");
  const openJobs = jobs.data?.filter((j) => j.status === "open").length;
  const awaitingReview = jobs.data?.filter((j) => j.last_run_status === "done" && (j.submit_count ?? 0) > 0).length;
  const pct = s && s.spend_cap_usd > 0 ? Math.min(100, (s.ai_spend_today_usd / s.spend_cap_usd) * 100) : 0;
  const firstName = user?.display_name.split(" ")[0];

  return (
    <div className="space-y-8">
      <PageHeader
        title={firstName ? `Welcome, ${firstName}` : "Welcome"}
        description="Here's where your candidate pool, job orders and approvals come together."
      />

      <section aria-label="Key numbers" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Candidates" value={formatNumber(s?.candidates)} caption="Profiles built from ingested resumes" icon={Users} loading={loading} href="/candidates" />
        <StatCard
          label="Needs attention"
          value={formatNumber(s?.needs_attention)}
          caption="Files a person needs to look at"
          icon={CircleAlert}
          loading={loading}
          href="/candidates?tab=attention"
        />
        <StatCard
          label="AI spend today"
          value={formatUsd(s?.ai_spend_today_usd)}
          caption={s ? `of ${formatUsd(s.spend_cap_usd)} daily cap · ${formatUsd(s.ai_spend_total_usd)} all time` : "Model and embedding cost, in USD"}
          icon={CircleDollarSign}
          loading={loading}
        >
          {s && <Progress value={pct} aria-label={`${pct.toFixed(0)}% of the daily spend cap used`} className="h-1.5" />}
        </StatCard>
        <StatCard label="Files processed" value={formatNumber(s?.files_processed)} caption="Resumes read, screened and extracted" icon={FileCheck2} loading={loading} />
        <StatCard
          label="Open job orders"
          value={formatNumber(openJobs)}
          caption="Searches your team is working"
          icon={BriefcaseBusiness}
          loading={jobs.loading && !jobs.data}
          href="/job-orders"
        />
        <StatCard
          label="Shortlists to review"
          value={formatNumber(awaitingReview)}
          caption="Job orders with candidates recommended to submit"
          icon={ListChecks}
          loading={jobs.loading && !jobs.data}
          href="/job-orders"
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <QualityBreakdown byQuality={s?.by_quality} loading={loading} />
        </div>
        <div className="lg:col-span-3">{children}</div>
      </div>
    </div>
  );
}
