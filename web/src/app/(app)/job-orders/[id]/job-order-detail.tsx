"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  CircleAlert,
  Info,
  Loader2,
  MessageCircleQuestion,
  MessagesSquare,
  Search,
  SearchX,
  Sparkles,
} from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { EmptyState } from "@/components/empty-state";
import { ResumeViewer, type ViewerTarget } from "@/components/resume-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, apiFetch, useApi } from "@/lib/api";
import { useUser } from "@/components/auth/user-provider";
import { capitalize, cleanRequirement, disciplineLabel, formatUsd, humanize, licenseLabel, relativeTime } from "@/lib/format";
import type { JobOrder, MatchesResponse, Requirement } from "@/lib/job-types";
import { cn } from "@/lib/utils";
import { Shortlist } from "./shortlist";

const POLL_MS = 2000;

function requirementBadge(r: Requirement): string | null {
  if (r.kind === "license" && r.key) return licenseLabel(r.state ? `${r.key}:${r.state}` : r.key);
  return null;
}

function Requirements({ items }: { items: Requirement[] }) {
  const groups = [
    { title: "Must have", items: items.filter((r) => r.priority === "must"), dot: "bg-brand", pill: "bg-brand-soft text-brand-strong ring-brand/20" },
    { title: "Nice to have", items: items.filter((r) => r.priority !== "must"), dot: "bg-muted-foreground/40", pill: "bg-muted text-muted-foreground ring-border" },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Requirements</CardTitle>
        <CardDescription>Must-haves weigh three times as much as nice-to-haves in the score.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {groups.map((g) =>
          g.items.length === 0 ? null : (
            <div key={g.title} className="space-y-2">
              <p className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset", g.pill)}>
                {g.title} <span className="tabular-nums">({g.items.length})</span>
              </p>
              <ul className="space-y-2">
                {g.items.map((r, i) => {
                  const badge = requirementBadge(r);
                  return (
                    <li key={i} className="flex gap-2.5 text-sm">
                      <span className={cn("mt-2 size-1.5 shrink-0 rounded-full", g.dot)} aria-hidden="true" />
                      <span className="min-w-0">
                        {cleanRequirement(r.text)}
                        {badge && (
                          <Badge variant="outline" className="ml-1.5 font-normal">
                            {badge}
                          </Badge>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ),
        )}
      </CardContent>
    </Card>
  );
}

function OpenQuestions({ questions }: { questions: string[] }) {
  const [done, setDone] = useState<Record<number, boolean>>({});
  if (questions.length === 0) return null;
  return (
    <Card className="border-warning/30 bg-warning-soft/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageCircleQuestion className="size-4 text-warning-strong" aria-hidden="true" /> Ask the hiring manager
        </CardTitle>
        <CardDescription>Things the notes didn&apos;t settle. Tick them off as you get answers.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {questions.map((q, i) => (
            <li key={i}>
              <label className="flex cursor-pointer items-start gap-2.5 text-sm">
                <input
                  type="checkbox"
                  checked={!!done[i]}
                  onChange={(e) => setDone((d) => ({ ...d, [i]: e.target.checked }))}
                  className="mt-0.5 size-4 shrink-0 accent-[var(--brand)]"
                />
                <span className={cn(done[i] && "text-muted-foreground line-through")}>{q}</span>
              </label>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function SpecCard({ jo }: { jo: JobOrder }) {
  const s = jo.spec;
  const rows: [string, string | null][] = [
    ["Location", [s.city, s.metro && s.metro !== s.city ? `${s.metro} metro` : null].filter(Boolean).join(" · ") || null],
    ["Discipline", s.discipline ? `${disciplineLabel(s.discipline)}${s.subdiscipline ? ` · ${humanize(s.subdiscipline)}` : ""}` : null],
    ["Work mode", s.work_mode ? humanize(s.work_mode) : null],
    ["Employment", s.employment_type ? humanize(s.employment_type) : null],
    ["Salary", s.salary],
    ["Experience", s.min_years !== null && s.min_years !== undefined ? `${s.min_years}+ years` : null],
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Role</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-2.5 text-sm">
          {rows.map(([k, v]) => (
            <div key={k} className="rounded-lg border bg-muted/40 px-3 py-2">
              <dt className="text-[11px] font-medium tracking-[0.04em] text-muted-foreground uppercase">{k}</dt>
              <dd className={cn("mt-0.5 font-medium", !v && "font-normal text-muted-foreground/70 italic")}>{v ?? "Not stated"}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

const MATCH_STAGES = [
  { at: 0, label: () => "Filtering candidates on hard requirements" },
  { at: 3000, label: () => "Searching resumes" },
  { at: 7000, label: (n: number | null) => `Scoring ${n ? `${n} ` : ""}candidates against each requirement` },
];

function MatchProgress({ startedAt, candidates }: { startedAt: number; candidates: number | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  const elapsed = Math.max(0, now - startedAt);
  const current = MATCH_STAGES.reduce((idx, s, i) => (elapsed >= s.at ? i : idx), 0);
  return (
    <Card>
      <CardContent className="space-y-2.5 py-2" role="status" aria-live="polite">
        {MATCH_STAGES.map((s, i) => (
          <p key={i} className={cn("flex items-center gap-2 text-sm", i > current && "text-muted-foreground/60")}>
            {i < current ? (
              <Check className="size-4 text-success" aria-hidden="true" />
            ) : i === current ? (
              <Loader2 className="size-4 animate-spin text-brand" aria-hidden="true" />
            ) : (
              <span className="flex size-4 items-center justify-center">
                <span className="size-1.5 rounded-full bg-muted-foreground/40" />
              </span>
            )}
            {s.label(candidates)}
            {i === current && "…"}
          </p>
        ))}
        <p className="text-xs text-muted-foreground tabular-nums">{Math.round(elapsed / 1000)} s · usually 20–40 s</p>
      </CardContent>
    </Card>
  );
}

function relaxedNotice(relaxed: string[]): string {
  const names = relaxed.map((r) => (r === "min_years" ? "years" : r === "license_codes" ? "license" : humanize(r).toLowerCase()));
  return `Few candidates met every hard requirement, so the ${names.join(" and ")} filter${names.length > 1 ? "s were" : " was"} loosened. Check those requirements in each checklist.`;
}

export function JobOrderDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const valid = /^\d+$/.test(id);
  const jo = useApi<JobOrder>(valid ? `/api/job-orders/${id}` : null);
  const matches = useApi<MatchesResponse>(valid ? `/api/job-orders/${id}/matches` : null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);
  const router = useRouter();
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const { user } = useUser();
  const isAdmin = user?.role === "admin";

  const noRun = matches.error?.status === 404; // treat "no run yet" like an empty result
  const run = matches.data?.run ?? null;
  const running = run?.status === "running";
  const { reload: reloadMatches, loading: matchesLoading } = matches;

  // Poll every 2 s while the latest run is still running.
  useEffect(() => {
    if (!running || matchesLoading) return;
    const t = setTimeout(reloadMatches, POLL_MS);
    return () => clearTimeout(t);
  }, [running, matchesLoading, reloadMatches]);

  async function findCandidates() {
    setStarting(true);
    setStartError(null);
    try {
      await apiFetch(`/api/job-orders/${id}/match`, { method: "POST" });
      reloadMatches();
    } catch (e) {
      setStartError(
        e instanceof ApiError && e.status === 429
          ? "Today's AI spend cap has been reached, so matching is paused until tomorrow."
          : e instanceof ApiError
            ? e.message
            : "Couldn't start matching. Try again.",
      );
    }
    setStarting(false);
  }

  // Opens a chat tied to this job order; the API seeds it with an assistant intro message.
  async function askAboutRole() {
    setOpening(true);
    try {
      const conv = await apiFetch<{ id: number }>("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_order_id: Number(id) }),
      });
      router.push(`/ask?c=${conv.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Couldn't open a chat. Try again.");
      setOpening(false);
    }
  }

  const back = (
    <Link href="/job-orders" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="size-4" aria-hidden="true" /> Job orders
    </Link>
  );

  if (!valid || jo.error?.status === 404) {
    return (
      <div className="space-y-6">
        {back}
        <Card className="py-0">
          <EmptyState icon={SearchX} title="Job order not found" description="It may have been removed." />
        </Card>
      </div>
    );
  }
  if (jo.error) return <div className="space-y-6">{back}<ApiErrorState error={jo.error} onRetry={jo.reload} /></div>;
  if (!jo.data) {
    return (
      <div className="space-y-6" aria-busy="true">
        {back}
        <Skeleton className="h-16 rounded-xl" />
        <div className="grid gap-6 lg:grid-cols-5">
          <Skeleton className="h-96 rounded-xl lg:col-span-2" />
          <Skeleton className="h-96 rounded-xl lg:col-span-3" />
        </div>
      </div>
    );
  }

  const j = jo.data;
  const busy = starting || running;
  return (
    <div className="space-y-6">
      {back}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl leading-tight font-semibold tracking-[-0.022em] sm:text-[26px]">{j.title}</h1>
          <p className="text-sm text-muted-foreground">
            {j.client ? capitalize(j.client) : "Client not stated"} · created {relativeTime(j.created_at)}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Button variant="outline" onClick={askAboutRole} disabled={opening}>
            {opening ? <Loader2 className="animate-spin" aria-hidden="true" /> : <MessagesSquare aria-hidden="true" />}
            Ask about this role
          </Button>
          <Button onClick={findCandidates} disabled={busy || (matches.data === undefined && !noRun)}>
            {busy ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
            {running ? "Matching…" : run ? "Run matching again" : "Find candidates"}
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          <SpecCard jo={j} />
          <Requirements items={j.spec.requirements} />
          <OpenQuestions questions={j.spec.open_questions} />
          <Collapsible>
            <Card className="gap-0 py-0">
              <CollapsibleTrigger className="group flex w-full items-center justify-between rounded-xl px-4 py-3 text-left text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
                Original call notes
                <ChevronDown className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" aria-hidden="true" />
              </CollapsibleTrigger>
              <CollapsibleContent>
                <pre className="border-t px-4 py-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground">{j.raw_notes}</pre>
              </CollapsibleContent>
            </Card>
          </Collapsible>
        </div>

        <section aria-labelledby="shortlist-heading" className="min-w-0 space-y-4 lg:col-span-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="shortlist-heading" className="text-base font-semibold tracking-[-0.01em]">
              Shortlist
            </h2>
            {run?.status === "done" && (
              <p className="text-xs text-muted-foreground tabular-nums">
                {run.candidates ?? matches.data?.matches.length} scored · {relativeTime(run.finished_at)}
                {isAdmin && run.cost_usd !== null && ` · ${formatUsd(run.cost_usd)}`}
              </p>
            )}
          </div>

          {startError && (
            <p role="alert" className="flex items-center gap-2 rounded-lg border border-danger/25 bg-danger-soft px-3 py-2 text-sm text-danger-strong">
              <CircleAlert className="size-4 shrink-0" aria-hidden="true" /> {startError}
            </p>
          )}
          {run && run.relaxed.length > 0 && (
            <p className="flex gap-2 rounded-lg border border-info/25 bg-info-soft px-3 py-2 text-sm text-info-strong">
              <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> {relaxedNotice(run.relaxed)}
            </p>
          )}
          {run?.status === "failed" && (
            <p role="alert" className="flex gap-2 rounded-lg border border-danger/25 bg-danger-soft px-3 py-2 text-sm text-danger-strong">
              <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> Matching failed{run.error ? `: ${run.error}` : ""}. Try running it again.
            </p>
          )}

          {matches.error && !noRun ? (
            <ApiErrorState error={matches.error} onRetry={matches.reload} />
          ) : matches.data === undefined && !noRun ? (
            <Skeleton className="h-64 rounded-xl" />
          ) : running && run ? (
            <MatchProgress startedAt={new Date(run.started_at).getTime()} candidates={run.candidates} />
          ) : matches.data && matches.data.matches.length > 0 ? (
            <Shortlist key={run?.run_id} matches={matches.data.matches} onViewResume={setViewer} />
          ) : (
            <Card className="py-0">
              <EmptyState
                icon={Search}
                title={run ? "No candidates matched" : "No shortlist yet"}
                description={
                  run
                    ? "Nobody in the pool met the hard requirements. Consider loosening the job order."
                    : "Find candidates to get a ranked shortlist, with every requirement checked against the resume."
                }
              />
            </Card>
          )}
        </section>
      </div>
      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
    </div>
  );
}
