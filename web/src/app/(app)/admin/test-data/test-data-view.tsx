"use client";

import { Fragment, useEffect, useState } from "react";
import {
  BriefcaseBusiness,
  ChevronDown,
  CircleAlert,
  Database,
  Eye,
  FileStack,
  FileUp,
  Layers,
  ListRestart,
  Loader2,
  RotateCcw,
  Sparkles,
  TriangleAlert,
  Users,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { ApiErrorState } from "@/components/api-state";
import { useUser } from "@/components/auth/user-provider";
import { EmptyState } from "@/components/empty-state";
import { IconTile, PageHeader } from "@/components/page-header";
import { qualityStyle } from "@/components/quality-badge";
import { ResumeViewer, type ViewerTarget } from "@/components/resume-viewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, apiFetch, useApi, type Stats } from "@/lib/api";
import type { JobOrderRow } from "@/lib/job-types";
import { disciplineLabel, formatNumber, humanize, licenseLabel, qualityLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

type Progress = {
  stage: string; status: string; total: number; done: number; ok: number; rejected: number;
  retried: number; cost_usd: number; elapsed_s: number; eta_s: number | null; updated_at: string;
};
type SeedStats = {
  candidates: number; people: number; written: number; rendered: number; job_orders: number;
  by_discipline: Record<string, number>; by_metro: Record<string, number>; by_format: Record<string, number>;
  by_split: Record<string, number>; credentials: Record<string, number>; tricky: Record<string, number>;
  quality?: Record<string, number>;
  updated_at: string;
};
type Showcase = {
  candidate_id: string; name: string; discipline: string; city: string; metro: string; years_experience: number;
  current_title: string; current_employer: string; license_codes: string[]; credential_texts: string[];
  software: string[]; tricky: string[]; quality: string; quality_issues: string[]; file: string; file_format: string; template: string; note: string;
  text_preview: string;
};
type SeedJobOrder = { job_order_id: string; title: string; split: string; notes: string | null; spec: Record<string, unknown> | null };
type SeedStatus = { progress: Progress | null; stats: SeedStats | null; showcase: Showcase[]; job_orders: SeedJobOrder[] };

const nice = (s: string) => s.replace(/_/g, " ");
const fmtSecs = (s: number | null) => (s == null ? "–" : s < 90 ? `${Math.round(s)}s` : `${Math.round(s / 60)} min`);
const QUEUE_ORDER = ["queued", "running", "done", "duplicate", "needs_attention", "failed"];
const QUEUE_DOT: Record<string, string> = {
  queued: "bg-info",
  running: "bg-brand",
  done: "bg-success",
  duplicate: "bg-muted-foreground",
  needs_attention: "bg-warning",
  failed: "bg-danger",
};

/** Polls the dev seed status (it only exists when the API runs with APP_ENV=dev). */
function useSeedStatus() {
  const [data, setData] = useState<SeedStatus | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const json = await apiFetch<SeedStatus>("/api/dev/seed/status");
        if (alive) {
          setData(json);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e instanceof ApiError ? e : new ApiError(0, "Can't reach the API"));
      }
    };
    load();
    const t = setInterval(load, 3000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  return { data, error };
}

/** Re-fetches a useApi resource on an interval, so the status cards stay live during an ingest. */
function usePolling(reload: () => void, ms: number) {
  useEffect(() => {
    const t = setInterval(reload, ms);
    return () => clearInterval(t);
  }, [reload, ms]);
}

function StatusCard({
  label,
  value,
  caption,
  icon,
  tone = "brand",
  loading,
  children,
}: {
  label: string;
  value: string;
  caption: React.ReactNode;
  icon: LucideIcon;
  tone?: "brand" | "success" | "warning" | "info" | "tamper";
  loading: boolean;
  children?: React.ReactNode;
}) {
  return (
    <Card className="h-full gap-3">
      <CardContent className="flex h-full flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[13px] font-medium text-muted-foreground">{label}</span>
          <IconTile icon={icon} tone={tone} size="sm" />
        </div>
        <div className="text-[28px] leading-none font-semibold tracking-[-0.02em] tabular-nums">{loading ? <Skeleton className="h-7 w-20" /> : value}</div>
        {children}
        <div className="mt-auto text-xs leading-snug text-muted-foreground">{loading ? <Skeleton className="h-3 w-32" /> : caption}</div>
      </CardContent>
    </Card>
  );
}

const BAR_LIMIT = 10;

function Bars({ title, data, total, label = nice }: { title: string; data: Record<string, number>; total: number; label?: (k: string) => string }) {
  const [all, setAll] = useState(false);
  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const entries = all ? sorted : sorted.slice(0, BAR_LIMIT);
  return (
    <Card className="gap-3 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data yet</p>
        ) : (
          <ul className="space-y-2">
            {entries.map(([k, v]) => (
              <li key={k} className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-2 text-[13px]">
                <span className="truncate" title={label(k)}>
                  {label(k)}
                </span>
                <span className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <span className="block h-full rounded-full bg-chart-1" style={{ width: `${Math.max(2, (v / Math.max(total, 1)) * 100)}%` }} />
                </span>
                <span className="text-right text-muted-foreground tabular-nums">{v}</span>
              </li>
            ))}
          </ul>
        )}
        {sorted.length > BAR_LIMIT && (
          <Button variant="ghost" size="xs" className="mt-2 -ml-2 text-muted-foreground" onClick={() => setAll((a) => !a)} aria-expanded={all}>
            {all ? "Show fewer" : `Show all ${sorted.length}`}
            <ChevronDown className={cn("transition-transform", all && "rotate-180")} aria-hidden="true" />
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

const tidy = (k: string) => humanize(k.replace(/_/g, " "));

type Action = {
  key: string;
  title: string;
  body: string;
  icon: LucideIcon;
  path: string;
  confirmTitle: string;
  confirmBody: string;
  confirmLabel: string;
  danger?: boolean;
  /** Text the admin must type before a destructive action is allowed. */
  typeToConfirm?: string;
  done: (r: Record<string, unknown>) => string;
};

const ACTIONS: Action[] = [
  {
    key: "ingest",
    title: "Queue synthetic resumes",
    body: "Puts every generated resume on the ingest queue. Already-queued files are skipped.",
    icon: FileUp,
    path: "/api/dev/ingest/seed",
    confirmTitle: "Queue all synthetic resumes for ingest?",
    confirmBody:
      "The workers will parse, screen and extract each new resume. Files already processed come from the extraction cache at no cost; new ones cost about $0.02 each and count toward the daily spend cap.",
    confirmLabel: "Queue resumes",
    done: (r) => `Queued ${r.queued ?? 0} resumes (${r.already_queued ?? 0} already queued).`,
  },
  {
    key: "jobs",
    title: "Load job orders",
    body: "Creates job orders from the synthetic hiring-manager notes. Existing ones are skipped.",
    icon: BriefcaseBusiness,
    path: "/api/dev/job-orders/seed",
    confirmTitle: "Load the synthetic job orders?",
    confirmBody: "Each new job order is structured from its notes by Claude (a paid call). Job orders that already exist are skipped, so this is safe to repeat.",
    confirmLabel: "Load job orders",
    done: (r) => `Created ${r.created ?? 0} job orders (${r.skipped_existing ?? 0} already existed).`,
  },
  {
    key: "retry",
    title: "Retry failed jobs",
    body: "Puts failed ingest jobs back on the queue, for example after fixing a configuration problem.",
    icon: ListRestart,
    path: "/api/ingest/jobs/retry-failed",
    confirmTitle: "Retry all failed ingest jobs?",
    confirmBody: "Failed jobs go back to the queue with their attempts reset. Retries may make paid extraction calls.",
    confirmLabel: "Retry failed",
    done: (r) => `Re-queued ${r.requeued ?? 0} failed jobs.`,
  },
  {
    key: "reset",
    title: "Reset ingested data",
    body: "Deletes people, resume files, profiles, search sections and ingest jobs so everything can be re-ingested.",
    icon: RotateCcw,
    path: "/api/dev/ingest/reset?confirm=yes",
    confirmTitle: "Delete all ingested candidates?",
    confirmBody:
      "This permanently removes every person, resume file, profile, search section and ingest job. The extraction cache and the AI cost log are kept, so a re-ingest costs nothing. Job orders are kept, but every match (shortlist entry) is deleted with the candidates.",
    confirmLabel: "Delete ingested data",
    danger: true,
    typeToConfirm: "RESET",
    done: () => "Ingested data deleted. Queue the synthetic resumes again to rebuild it.",
  },
];

function ActionRow({ a, onDone }: { a: Action; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const ready = !a.typeToConfirm || typed.trim() === a.typeToConfirm;

  const run = async () => {
    setBusy(true);
    try {
      const r = await apiFetch<Record<string, unknown>>(a.path, { method: "POST" });
      toast.success(a.done(r));
      setOpen(false);
      onDone();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-col gap-3 py-3.5 first:pt-0 last:pb-0 sm:flex-row sm:items-center">
      <IconTile icon={a.icon} tone={a.danger ? "danger" : "brand"} size="sm" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{a.title}</p>
        <p className="text-xs leading-relaxed text-muted-foreground">{a.body}</p>
      </div>
      <Dialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o);
          if (!o) setTyped("");
        }}
      >
        <DialogTrigger asChild>
          <Button variant={a.danger ? "destructive" : "outline"} size="sm" className="self-start sm:self-auto">
            {a.title}
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {a.danger && <TriangleAlert className="size-4 text-danger-strong" aria-hidden="true" />}
              {a.confirmTitle}
            </DialogTitle>
            <DialogDescription>{a.confirmBody}</DialogDescription>
          </DialogHeader>
          {a.typeToConfirm && (
            <label className="space-y-1.5 text-sm">
              <span>
                Type <span className="font-mono font-semibold">{a.typeToConfirm}</span> to confirm
              </span>
              <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" aria-label={`Type ${a.typeToConfirm} to confirm`} />
            </label>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant={a.danger ? "destructive" : "default"}
              onClick={run}
              disabled={!ready || busy}
              className={cn(a.danger && "bg-destructive text-white hover:bg-destructive/90 dark:bg-destructive dark:hover:bg-destructive/90")}
            >
              {busy && <Loader2 className="animate-spin" aria-hidden="true" />}
              {a.confirmLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </li>
  );
}

function SectionTitle({ title, note }: { title: string; note?: string }) {
  return (
    <h2 className="text-[15px] font-semibold tracking-[-0.01em]">
      {title}
      {note && <span className="ml-2 text-xs font-normal text-muted-foreground">{note}</span>}
    </h2>
  );
}

const HEADER_PROPS = {
  icon: Database,
  eyebrow: "Admin · Dev only",
  title: "Test data",
  description:
    "Synthetic A/E/C candidates and job orders used to build and test Placewise. Facts are generated by code, so the right answers are known; resumes are written by Claude Haiku, fact-checked and rendered to PDF, DOCX and TXT with real-world messiness.",
};

/** Admin-only, like the other admin pages: recruiters get the "Admins only" state without any request. */
export function TestDataView() {
  const { user } = useUser();
  if (!user) {
    return (
      <div className="space-y-6">
        <PageHeader {...HEADER_PROPS} />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-36 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }
  if (user.role !== "admin") {
    return (
      <div className="space-y-6">
        <PageHeader {...HEADER_PROPS} />
        <ApiErrorState error={new ApiError(403, "Admins only")} />
      </div>
    );
  }
  return <AdminTestData />;
}

function AdminTestData() {
  const seed = useSeedStatus();
  const stats = useApi<Stats>("/api/stats");
  const jobs = useApi<JobOrderRow[]>("/api/job-orders");
  usePolling(stats.reload, 5000);
  const [open, setOpen] = useState<string | null>(null);
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const [samples, setSamples] = useState<string[]>([]);

  useEffect(() => {
    apiFetch<string[]>("/api/dev/seed/samples").then(setSamples).catch(() => {});
  }, []);

  const header = <PageHeader {...HEADER_PROPS} />;

  if (seed.error && seed.error.status === 403) {
    return (
      <div className="space-y-6">
        {header}
        <ApiErrorState error={seed.error} />
      </div>
    );
  }
  if (seed.error && !seed.data) {
    return (
      <div className="space-y-6">
        {header}
        <Card className="py-0">
          <EmptyState
            icon={CircleAlert}
            tone="muted"
            title="Test data tools are off"
            description="The seed API runs only in dev mode (APP_ENV=dev), so this page has nothing to show here."
          />
        </Card>
      </div>
    );
  }

  const s = seed.data?.stats ?? null;
  const p = seed.data?.progress ?? null;
  const showcase = seed.data?.showcase ?? [];
  const seedJobs = seed.data?.job_orders ?? [];
  const st = stats.error ? undefined : stats.data;
  const queue = st?.ingest_jobs ?? {};
  const queueEntries = [...QUEUE_ORDER.filter((k) => k in queue), ...Object.keys(queue).filter((k) => !QUEUE_ORDER.includes(k))].map((k) => [k, queue[k]] as const);
  const queueTotal = queueEntries.reduce((t, [, n]) => t + n, 0);
  const active = (queue.queued ?? 0) + (queue.running ?? 0);
  const pct = p && p.total ? Math.round((p.done / p.total) * 100) : 0;
  const seedLoading = !seed.data;
  const refresh = () => {
    stats.reload();
    jobs.reload();
  };

  return (
    <div className="space-y-8">
      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
      {header}

      <section aria-label="Status" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard
          label="Synthetic candidates"
          value={formatNumber(s?.candidates)}
          caption={s ? `${formatNumber(s.people)} unique people · ${formatNumber(s.rendered)} files rendered` : "Generator hasn't run yet"}
          icon={Sparkles}
          tone="tamper"
          loading={seedLoading}
        />
        <StatusCard
          label="Resumes ingested"
          value={formatNumber(st?.files_processed)}
          caption={st ? `${formatNumber(st.candidates)} candidate profiles · ${formatNumber(st.needs_attention)} need attention` : "From the ingest pipeline"}
          icon={Users}
          loading={stats.loading && !stats.data}
        />
        <StatusCard
          label="Job orders loaded"
          value={formatNumber(jobs.data?.length)}
          caption={s ? `of ${formatNumber(s.job_orders)} synthetic job orders` : "In the portal"}
          icon={BriefcaseBusiness}
          tone="info"
          loading={jobs.loading && !jobs.data}
        />
        <StatusCard
          label="Ingest queue"
          value={active > 0 ? `${formatNumber(active)} active` : "Idle"}
          caption={
            queueTotal ? (
              <ul className="flex flex-wrap gap-x-3 gap-y-1">
                {queueEntries.map(([k, n]) => (
                  <li key={k} className="flex items-center gap-1.5">
                    <span className={cn("size-1.5 rounded-full", QUEUE_DOT[k] ?? "bg-muted-foreground")} aria-hidden="true" />
                    {nice(k)} <span className="font-medium text-foreground tabular-nums">{formatNumber(n)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              "No ingest jobs yet"
            )
          }
          icon={Layers}
          tone={active > 0 ? "warning" : "success"}
          loading={stats.loading && !stats.data}
        >
          {queueTotal > 0 && (
            <div className="flex h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
              {queueEntries.map(([k, n]) => (
                <span key={k} className={QUEUE_DOT[k] ?? "bg-muted-foreground"} style={{ width: `${(n / queueTotal) * 100}%` }} />
              ))}
            </div>
          )}
        </StatusCard>
      </section>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Actions</CardTitle>
            <CardDescription>Each one asks for confirmation first. Paid steps count toward the daily AI spend cap.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {ACTIONS.map((a) => (
                <ActionRow key={a.key} a={a} onDone={refresh} />
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Last generator run</CardTitle>
            <CardDescription>Writing and rendering the synthetic resumes (run from the command line).</CardDescription>
          </CardHeader>
          <CardContent>
            {seedLoading ? (
              <Skeleton className="h-28" />
            ) : !p ? (
              <p className="text-sm text-muted-foreground">No generator run recorded.</p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium capitalize">{p.stage}</p>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-xs font-medium",
                      p.status === "running" ? "bg-warning-soft text-warning-strong" : "bg-success-soft text-success-strong",
                    )}
                  >
                    {p.status === "running" ? "Running" : "Done"}
                  </span>
                </div>
                <div role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Generator progress" className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-brand transition-[width]" style={{ width: `${pct}%` }} />
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                  {[
                    ["Done", `${formatNumber(p.done)} / ${formatNumber(p.total)} (${pct}%)`],
                    ["Passed fact check", formatNumber(p.ok)],
                    ["Self-corrected on retry", formatNumber(p.retried)],
                    ["Rejected", formatNumber(p.rejected)],
                    ["Cost", `$${p.cost_usd.toFixed(3)}`],
                    [p.status === "running" ? "Time left" : "Elapsed", p.status === "running" ? fmtSecs(p.eta_s) : fmtSecs(p.elapsed_s)],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-muted-foreground">{k}</dt>
                      <dd className="font-medium tabular-nums">{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {s && (
        <section className="space-y-3">
          <SectionTitle title="What's in the dataset" note={`Dev / test split by person: ${s.by_split.dev ?? 0} / ${s.by_split.test ?? 0}`} />
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Bars title="Discipline" data={s.by_discipline} total={s.candidates} label={disciplineLabel} />
            <Bars title="Metro" data={s.by_metro} total={s.candidates} label={(k) => k} />
            <Bars title="Credentials actually held" data={s.credentials} total={s.candidates} label={licenseLabel} />
            <Bars title="Edge cases built in" data={s.tricky} total={s.candidates} label={tidy} />
            {s.quality && <Bars title="Resume quality (deliberate, labeled)" data={Object.fromEntries(Object.entries(s.quality).map(([k, v]) => [qualityLabel(k, true), v]))} total={s.candidates} label={(k) => k} />}
            <Bars title="File formats" data={s.by_format} total={s.rendered} label={(k) => k.toUpperCase()} />
          </div>
        </section>
      )}

      {samples.length > 0 && (
        <section className="space-y-3">
          <SectionTitle title="Template samples" note="One per resume layout, for review" />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {samples.map((name) => {
              const label = name.startsWith("two_column") ? "Two column" : name.startsWith("ats_plain") ? "ATS plain" : nice(name.split("_")[0]);
              const person = name.replace(".pdf", "").split("_").slice(-2).join(" ");
              return (
                <button
                  key={name}
                  type="button"
                  onClick={() =>
                    setViewer({ title: person, subtitle: `${label} template`, viewUrl: `/api/dev/seed/samples/${name}`, downloadUrl: `/api/dev/seed/samples/${name}?download=true` })
                  }
                  className="group/sample flex items-center gap-3 rounded-xl border bg-card p-3.5 text-left shadow-xs transition-[box-shadow,border-color,transform] duration-150 outline-none hover:-translate-y-px hover:border-brand/30 hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/40"
                >
                  <IconTile icon={FileStack} size="sm" />
                  <span className="min-w-0">
                    <span className="block text-xs font-semibold tracking-wide text-brand uppercase">{label}</span>
                    <span className="block truncate text-sm font-medium capitalize">{person}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <SectionTitle title="Showcase candidates" note="Dev split, so the true answers are shown" />
        <Card className="gap-0 py-0">
          {showcase.length === 0 ? (
            <EmptyState icon={Users} tone="muted" title="No samples yet" description="Showcase candidates appear after the resumes are rendered." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-muted/40 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  <tr>
                    {["Candidate", "Discipline", "Experience", "True credentials", "Quality", "File"].map((h) => (
                      <th key={h} className="h-10 px-4 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {showcase.map((c) => (
                    <Fragment key={c.candidate_id}>
                      <tr className="align-top transition-colors hover:bg-muted/40">
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={() => setOpen(open === c.candidate_id ? null : c.candidate_id)}
                            aria-expanded={open === c.candidate_id}
                            className="inline-flex items-center gap-1 rounded text-left font-medium outline-none hover:text-brand focus-visible:ring-3 focus-visible:ring-ring/40"
                          >
                            {c.name}
                            <ChevronDown className={cn("size-3.5 text-muted-foreground transition-transform", open === c.candidate_id && "rotate-180")} aria-hidden="true" />
                          </button>
                          <p className="text-xs text-muted-foreground">
                            {c.current_title} · {c.current_employer}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {c.city} ({c.metro})
                          </p>
                        </td>
                        <td className="px-4 py-3">{disciplineLabel(c.discipline)}</td>
                        <td className="px-4 py-3 tabular-nums">{c.years_experience} yrs</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            {c.license_codes.length ? (
                              c.license_codes.map((l) => (
                                <span key={l} className="rounded-md bg-success-soft px-1.5 py-0.5 text-xs font-medium text-success-strong">
                                  {licenseLabel(l)}
                                </span>
                              ))
                            ) : (
                              <span className="text-xs text-muted-foreground">none</span>
                            )}
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">as written: {c.credential_texts.join("; ") || "–"}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn("inline-block rounded-md px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset", qualityStyle(c.quality).badge)}>
                            {qualityLabel(c.quality, true)}
                            {c.quality !== "polished" && " (on purpose)"}
                          </span>
                          {c.quality_issues.length > 0 && <p className="mt-1 text-xs text-muted-foreground">{c.quality_issues.map(nice).join(", ")}</p>}
                          {c.note && <p className="text-xs text-muted-foreground">{c.note}</p>}
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            variant="outline"
                            size="xs"
                            onClick={() =>
                              setViewer({
                                title: c.name,
                                subtitle: `${c.candidate_id} · ${c.template} template`,
                                viewUrl: `/api/dev/seed/files/${c.candidate_id}/view`,
                                downloadUrl: `/api/dev/seed/files/${c.candidate_id}`,
                              })
                            }
                          >
                            <Eye aria-hidden="true" /> View resume
                          </Button>
                          <p className="mt-1 text-xs text-muted-foreground">{c.template} template</p>
                        </td>
                      </tr>
                      {open === c.candidate_id && (
                        <tr>
                          <td colSpan={6} className="bg-muted/40 px-4 py-3">
                            <p className="mb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">Resume text (first 1,500 characters, after noise)</p>
                            <pre className="max-h-80 overflow-auto font-mono text-xs whitespace-pre-wrap">{c.text_preview}</pre>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      <section className="space-y-3">
        <SectionTitle title="Synthetic job orders" note="The hiring-manager notes each job order starts from" />
        {seedJobs.length === 0 ? (
          <Card className="py-0">
            <EmptyState icon={BriefcaseBusiness} tone="muted" title="No job orders generated" description="Job orders are generated after the candidates." />
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {seedJobs.map((j) => (
              <Card key={j.job_order_id} className="gap-2 py-4">
                <CardHeader className="px-4">
                  <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="rounded-md bg-brand-soft px-1.5 py-0.5 font-mono text-[11px] text-brand-strong">{j.job_order_id}</span>
                    {j.title}
                    <span className="text-xs font-normal text-muted-foreground">{j.split} split</span>
                  </CardTitle>
                </CardHeader>
                {j.notes && (
                  <CardContent className="px-4">
                    <p className="line-clamp-6 text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground">{j.notes}</p>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
