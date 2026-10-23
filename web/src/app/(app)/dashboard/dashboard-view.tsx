"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import {
  ArrowRight,
  BriefcaseBusiness,
  CircleCheck,
  CircleDollarSign,
  FileUp,
  FileWarning,
  ListChecks,
  MessageSquareText,
  Plus,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useUser } from "@/components/auth/user-provider";
import { IconTile, PageHeader } from "@/components/page-header";
import { qualityStyle } from "@/components/quality-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi, type Stats } from "@/lib/api";
import type { JobOrderRow } from "@/lib/job-types";
import { capitalize, formatNumber, formatUsd, qualityLabel, relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { UploadDialog } from "../candidates/upload-dialog";
import { NewJobOrderDialog } from "../job-orders/new-job-order-dialog";

const QUALITY_ORDER = ["polished", "flawed", "adversarial", "unusable"];
const QUALITY_STROKE: Record<string, string> = {
  polished: "stroke-success",
  flawed: "stroke-warning",
  adversarial: "stroke-tamper",
  unusable: "stroke-danger",
};
const QUALITY_HELP: Record<string, string> = {
  polished: "Well-structured, ready to use",
  flawed: "Readable, with typos, vague bullet points or gaps",
  adversarial: "Hidden instructions aimed at AI, removed before reading",
  unusable: "Scanned or damaged files that need a person",
};

// ---- Greeting: computed in the browser, in Central time (the recruiting team is in DFW). ----
const TZ = "America/Chicago";
const subscribeMinute = (cb: () => void) => {
  const t = setInterval(cb, 60_000);
  return () => clearInterval(t);
};
function chicagoHour(): number {
  return Number(new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone: TZ }).format(new Date()));
}
function useGreeting(): { greeting: string | null; date: string | null } {
  // Server snapshot is null, so the server HTML never guesses the visitor's time of day.
  const hour = useSyncExternalStore(subscribeMinute, chicagoHour, () => null);
  const date = useSyncExternalStore(
    subscribeMinute,
    () => new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: TZ }).format(new Date()),
    () => null,
  );
  if (hour === null) return { greeting: null, date: null };
  const greeting = hour < 5 ? "Good evening" : hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  return { greeting, date };
}

// ---- KPI card ----
function StatCard({
  label,
  value,
  caption,
  icon,
  tone = "brand",
  loading,
  href,
  children,
}: {
  label: string;
  value: string;
  caption: React.ReactNode;
  icon: LucideIcon;
  tone?: "brand" | "success" | "warning" | "info";
  loading: boolean;
  href?: string;
  children?: React.ReactNode;
}) {
  const body = (
    <Card
      className={cn(
        "h-full gap-3 transition-[box-shadow,border-color,transform] duration-150",
        href && "group-hover/stat:-translate-y-px group-hover/stat:border-foreground/15 group-hover/stat:shadow-md",
      )}
    >
      <CardContent className="flex h-full flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[13px] font-medium text-muted-foreground">{label}</span>
          <IconTile icon={icon} tone={tone} size="sm" />
        </div>
        <div className="text-[28px] leading-none font-semibold tracking-[-0.02em] tabular-nums">
          {loading ? <Skeleton className="h-7 w-20" /> : value}
        </div>
        {children}
        <p className="mt-auto flex items-center gap-1 text-xs text-muted-foreground">
          {caption}
          {href && (
            <ArrowRight
              className="ml-auto size-3.5 -translate-x-1 opacity-0 transition-[opacity,transform] duration-150 group-hover/stat:translate-x-0 group-hover/stat:opacity-100"
              aria-hidden="true"
            />
          )}
        </p>
      </CardContent>
    </Card>
  );
  return href ? (
    <Link href={href} className="group/stat rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/40">
      {body}
    </Link>
  ) : (
    body
  );
}

// ---- Resume quality: donut + legend ----
function Donut({ entries, total }: { entries: (readonly [string, number])[]; total: number }) {
  const r = 42;
  const c = 2 * Math.PI * r;
  const gap = entries.length > 1 ? 2.5 : 0; // surface gap between segments
  const lens = entries.map(([, n]) => (total ? (n / total) * c : 0));
  const starts = lens.map((_, i) => lens.slice(0, i).reduce((a, b) => a + b, 0));
  return (
    <div className="relative size-40 shrink-0">
      <svg viewBox="0 0 100 100" className="size-full -rotate-90" aria-hidden="true">
        <circle cx="50" cy="50" r={r} fill="none" strokeWidth="11" className="stroke-muted" />
        {entries.map(([q], i) => {
          const len = lens[i];
          return (
            <circle
              key={q}
              cx="50"
              cy="50"
              r={r}
              fill="none"
              strokeWidth="11"
              className={QUALITY_STROKE[q] ?? "stroke-muted-foreground"}
              strokeDasharray={`${Math.max(0, len - gap)} ${c}`}
              strokeDashoffset={-starts[i]}
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tracking-[-0.02em] tabular-nums">{formatNumber(total)}</span>
        <span className="text-xs text-muted-foreground">files screened</span>
      </div>
    </div>
  );
}

function QualityBreakdown({ byQuality, loading }: { byQuality?: Record<string, number>; loading: boolean }) {
  const entries = byQuality
    ? [...QUALITY_ORDER.filter((q) => q in byQuality), ...Object.keys(byQuality).filter((q) => !QUALITY_ORDER.includes(q))].map(
        (q) => [q, byQuality[q]] as const,
      )
    : [];
  const total = entries.reduce((s, [, n]) => s + n, 0);
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Resume quality</CardTitle>
        <CardDescription>How every processed file was classified before extraction.</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-6">
            <Skeleton className="size-40 rounded-full" />
            <div className="flex-1 space-y-3">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-6" />
              ))}
            </div>
          </div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No files processed yet.</p>
        ) : (
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
            <Donut entries={entries} total={total} />
            <ul className="w-full min-w-0 flex-1 divide-y">
              {entries.map(([q, n]) => (
                <li key={q} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                  <span className={cn("size-2.5 shrink-0 rounded-[3px]", qualityStyle(q).dot)} aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{qualityLabel(q, true)}</p>
                    <p className="truncate text-xs text-muted-foreground">{QUALITY_HELP[q]}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold tabular-nums">{formatNumber(n)}</p>
                    <p className="text-xs text-muted-foreground tabular-nums">{total ? ((n / total) * 100).toFixed(1) : 0}%</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---- Needs your attention ----
function AttentionRow({
  href,
  icon,
  tone,
  title,
  meta,
  count,
}: {
  href: string;
  icon: LucideIcon;
  tone: "brand" | "warning" | "success";
  title: string;
  meta: string;
  count?: number;
}) {
  return (
    <li>
      <Link
        href={href}
        className="group/row -mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors duration-150 outline-none hover:bg-muted/60 focus-visible:ring-3 focus-visible:ring-ring/40"
      >
        <IconTile icon={icon} tone={tone} size="sm" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{title}</p>
          <p className="truncate text-xs text-muted-foreground">{meta}</p>
        </div>
        {count !== undefined && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold tabular-nums">{formatNumber(count)}</span>
        )}
        <ArrowRight
          className="size-4 shrink-0 text-muted-foreground transition-transform duration-150 group-hover/row:translate-x-0.5"
          aria-hidden="true"
        />
      </Link>
    </li>
  );
}

function NeedsAttention({ toReview, needsAttention, loading }: { toReview?: JobOrderRow[]; needsAttention?: number; loading: boolean }) {
  const top = (toReview ?? []).slice(0, 4);
  const more = (toReview?.length ?? 0) - top.length;
  const nothing = !loading && top.length === 0 && !needsAttention;
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Needs your attention</CardTitle>
        <CardDescription>Shortlists waiting for a decision and files a person should check.</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-11" />
            ))}
          </div>
        ) : nothing ? (
          <div className="flex items-center gap-3 rounded-lg bg-success-soft px-3 py-3 text-sm text-success-strong">
            <CircleCheck className="size-4 shrink-0" aria-hidden="true" /> You&apos;re all caught up.
          </div>
        ) : (
          <ul>
            {top.map((j) => (
              <AttentionRow
                key={j.id}
                href={`/job-orders/${j.id}`}
                icon={ListChecks}
                tone="brand"
                title={j.title}
                meta={`${j.client ? `${capitalize(j.client)} · ` : ""}${j.submit_count} suggested to submit · matched ${relativeTime(j.last_run_at)}`}
              />
            ))}
            {more > 0 && (
              <AttentionRow href="/job-orders" icon={BriefcaseBusiness} tone="brand" title={`${more} more shortlists to review`} meta="See all job orders" />
            )}
            {!!needsAttention && (
              <AttentionRow
                href="/candidates?tab=attention"
                icon={FileWarning}
                tone="warning"
                title="Resumes needing attention"
                meta="Scanned or damaged files that couldn't become a profile"
                count={needsAttention}
              />
            )}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ---- Quick actions ----
function ActionTile({ icon: Icon, title, body, ...rest }: { icon: LucideIcon; title: string; body: string } & React.ComponentProps<"button">) {
  return (
    <button
      type="button"
      {...rest}
      className="group/action flex w-full items-center gap-3 rounded-xl border bg-card p-3.5 text-left shadow-xs transition-[box-shadow,border-color,transform] duration-150 outline-none hover:-translate-y-px hover:border-brand/30 hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/40"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-[inset_0_1px_0_0_oklch(1_0_0/0.2)]">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{title}</span>
        <span className="block truncate text-xs text-muted-foreground">{body}</span>
      </span>
      <ArrowRight
        className="size-4 shrink-0 text-muted-foreground transition-transform duration-150 group-hover/action:translate-x-0.5"
        aria-hidden="true"
      />
    </button>
  );
}

function QuickActions() {
  return (
    <section aria-labelledby="quick-actions" className="space-y-3">
      <h2 id="quick-actions" className="text-[15px] font-semibold tracking-[-0.01em]">
        Quick actions
      </h2>
      <div className="grid gap-3 sm:grid-cols-3 [&>*]:min-w-0">
        <NewJobOrderDialog trigger={<ActionTile icon={Plus} title="New job order" body="Paste notes from a hiring-manager call" />} />
        <UploadDialog trigger={<ActionTile icon={FileUp} title="Upload resume" body="PDF or Word, screened before AI reads it" />} />
        <Link
          href="/ask"
          className="group/action flex w-full items-center gap-3 rounded-xl border bg-card p-3.5 text-left shadow-xs transition-[box-shadow,border-color,transform] duration-150 outline-none hover:-translate-y-px hover:border-brand/30 hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/40"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-[inset_0_1px_0_0_oklch(1_0_0/0.2)]">
            <MessageSquareText className="size-4" aria-hidden="true" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium">Ask Placewise</span>
            <span className="block truncate text-xs text-muted-foreground">Questions about candidates, answered with citations</span>
          </span>
          <ArrowRight
            className="size-4 shrink-0 text-muted-foreground transition-transform duration-150 group-hover/action:translate-x-0.5"
            aria-hidden="true"
          />
        </Link>
      </div>
    </section>
  );
}

export function DashboardView({ children }: { children: React.ReactNode }) {
  const { user } = useUser();
  const { greeting, date } = useGreeting();
  const { data: stats, loading, error } = useApi<Stats>("/api/stats");
  const s = error ? undefined : stats;
  // Until /api/stats has job-order fields, derive them from the job-order list.
  const jobs = useApi<JobOrderRow[]>("/api/job-orders");
  const jobsLoading = jobs.loading && !jobs.data;
  const openJobs = jobs.data?.filter((j) => j.status === "open").length;
  const toReview = jobs.data
    ?.filter((j) => j.last_run_status === "done" && (j.submit_count ?? 0) > 0)
    .sort((a, b) => (b.last_run_at ?? "").localeCompare(a.last_run_at ?? ""));
  const pct = s && s.spend_cap_usd > 0 ? Math.min(100, (s.ai_spend_today_usd / s.spend_cap_usd) * 100) : 0;
  const firstName = user?.display_name.split(" ")[0];
  const title = `${greeting ?? "Welcome"}${firstName ? `, ${firstName}` : ""}`;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={date ?? " "}
        title={title}
        description="Your candidate pool, job orders and approvals in one place."
        actions={<NewJobOrderDialog />}
      />

      <section aria-label="Key numbers" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Candidates"
          value={formatNumber(s?.candidates)}
          caption={s ? `${formatNumber(s.files_processed)} resumes processed` : "Profiles built from ingested resumes"}
          icon={Users}
          loading={loading}
          href="/candidates"
        />
        <StatCard
          label="Open job orders"
          value={formatNumber(openJobs)}
          caption="Searches your team is working"
          icon={BriefcaseBusiness}
          tone="info"
          loading={jobsLoading}
          href="/job-orders"
        />
        <StatCard
          label="Shortlists to review"
          value={formatNumber(toReview?.length)}
          caption="With candidates suggested to submit"
          icon={ListChecks}
          tone="success"
          loading={jobsLoading}
          href="/job-orders"
        />
        <StatCard
          label="AI spend today"
          value={formatUsd(s?.ai_spend_today_usd)}
          caption={s ? `of ${formatUsd(s.spend_cap_usd)} daily cap · ${formatUsd(s.ai_spend_total_usd)} all time` : "Model and embedding cost, in USD"}
          icon={CircleDollarSign}
          tone="warning"
          loading={loading}
        >
          {s && (
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(pct)}
              aria-label={`${pct.toFixed(0)}% of the daily spend cap used`}
              className="h-1.5 overflow-hidden rounded-full bg-muted"
            >
              <div
                className={cn("h-full rounded-full transition-[width] duration-500", pct >= 90 ? "bg-danger" : pct >= 70 ? "bg-warning" : "bg-brand")}
                style={{ width: `${pct}%` }}
              />
            </div>
          )}
        </StatCard>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <NeedsAttention toReview={toReview} needsAttention={s?.needs_attention} loading={jobsLoading || loading} />
        <QualityBreakdown byQuality={s?.by_quality} loading={loading} />
      </div>

      <QuickActions />

      {children}
    </div>
  );
}
