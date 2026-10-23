"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  CalendarClock,
  CircleDollarSign,
  Database,
  FileText,
  Gauge,
  Hand,
  ListChecks,
  MessageSquareText,
  ShieldCheck,
  Wallet,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { useUser } from "@/components/auth/user-provider";
import { EmptyState } from "@/components/empty-state";
import { IconTile, PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, useApi, type Costs } from "@/lib/api";
import { formatNumber, formatUsd, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

const STEP_LABELS: Record<string, string> = {
  "rag.answer": "Ask: write cited answer",
  "rag.understand": "Ask: understand question",
  "ask.route": "Ask: route chat message",
  "voyage.embed_query": "Search: embed the query (Voyage)",
  "voyage.rerank": "Search: rerank results (Voyage)",
  "ingest.extract": "Resume extraction",
  "match.score": "Matching: score candidate",
  "job_order.extract": "Job order: structure notes",
};

const titleCase = (s: string) => s.replace(/[._-]+/g, " ").trim().replace(/\b\w/g, (c) => c.toUpperCase());

function stepLabel(step: string) {
  if (STEP_LABELS[step]) return STEP_LABELS[step];
  if (step.startsWith("seed.")) return `Test data: ${humanize(step.slice(5).replace(/[._-]+/g, " "))}`;
  return titleCase(step);
}

// Model chip colours: Sonnet = brand, Haiku = teal, Opus = violet, Voyage = amber, anything else muted.
function modelChip(model: string) {
  const m = model.toLowerCase();
  if (m.includes("sonnet")) return "bg-brand-soft text-brand-strong ring-brand/15";
  if (m.includes("haiku")) return "bg-success-soft text-success-strong ring-success/20";
  if (m.includes("opus")) return "bg-tamper-soft text-tamper-strong ring-tamper/20";
  if (m.includes("voyage") || m.includes("rerank")) return "bg-warning-soft text-warning-strong ring-warning/25";
  return "bg-muted text-muted-foreground ring-border";
}

// A matching run scores up to 12 candidates, one model call each (see the match graph).
const CANDIDATES_PER_SHORTLIST = 12;
const ASK_STEPS = ["rag.answer", "rag.understand", "ask.route"];

function shortDay(day: string) {
  // "2026-10-22" → "Oct 22" (parsed as a calendar date, not shifted by the local timezone)
  const [y, m, d] = day.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const usd = (v: number | null | undefined) => (v === null || v === undefined ? "–" : formatUsd(v, v > 0 && v < 0.1 ? 3 : 2));

function DayTooltip({ active, payload }: { active?: boolean; payload?: { payload: Costs["by_day"][number] }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <p className="font-medium">{shortDay(p.day)}</p>
      <p className="tabular-nums">{formatUsd(p.cost_usd)}</p>
      <p className="text-muted-foreground tabular-nums">{formatNumber(p.calls)} calls</p>
    </div>
  );
}

function ByDayChart({ days }: { days: Costs["by_day"] }) {
  const data = [...days].sort((a, b) => a.day.localeCompare(b.day));
  return (
    <div className="h-64 w-full" role="img" aria-label={`AI cost by day: ${data.map((d) => `${shortDay(d.day)} ${formatUsd(d.cost_usd)}`).join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 256 }}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="cost-bar" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={1} />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.7} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="day" tickFormatter={shortDay} tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} minTickGap={16} />
          <YAxis tickFormatter={(v: number) => `$${v}`} tickLine={false} axisLine={false} width={44} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
          <Tooltip content={<DayTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.6 }} isAnimationActive={false} />
          <Bar dataKey="cost_usd" fill="url(#cost-bar)" radius={[4, 4, 0, 0]} maxBarSize={44} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function KpiCard({
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

const CONTROLS: { title: string; body: string; icon: LucideIcon }[] = [
  { title: "Daily spend cap", body: "New AI calls are refused with a 429 once the cap is reached; queued resumes pause instead of failing.", icon: Gauge },
  { title: "Haiku for cheap steps", body: "Routing and question understanding use Claude Haiku 5.5; Sonnet only where quality needs it.", icon: Zap },
  { title: "Extraction cache", body: "Results are cached by a hash of the resume text, so a retry or re-ingest never pays twice.", icon: Database },
  { title: "Keyword shortcut", body: "Greetings like “hi” and “thanks” are answered by code: $0, no model call.", icon: Hand },
];

export function CostsView() {
  const { user } = useUser();
  // Recruiters get the "Admins only" state without a request (the API would answer 403 anyway).
  const isAdmin = user?.role === "admin";
  const api = useApi<Costs>(isAdmin ? "/api/admin/costs" : null);
  const { data, reload } = api;
  const loading = !data;
  const error = user && !isAdmin ? new ApiError(403, "Admins only") : api.error;

  const header = (
    <PageHeader icon={CircleDollarSign} eyebrow="Admin" title="AI costs" description="Every model and embedding call is logged with tokens and cost. Here is where the money goes." />
  );

  if (error && error.status !== 404)
    return (
      <div className="space-y-6">
        {header}
        <ApiErrorState error={error} onRetry={reload} />
      </div>
    );
  if (error || (data && data.by_day.length === 0 && data.by_step_model.length === 0 && data.spent_today_usd === 0)) {
    return (
      <div className="space-y-6">
        {header}
        <Card className="py-0">
          <EmptyState icon={CircleDollarSign} title="No AI usage recorded" description="Spend shows up here as soon as Placewise makes its first model call." />
        </Card>
      </div>
    );
  }

  const pct = data && data.spend_cap_usd > 0 ? (data.spent_today_usd / data.spend_cap_usd) * 100 : 0;
  const rows = data ? [...data.by_step_model].sort((a, b) => b.cost_usd - a.cost_usd) : [];
  const totals = rows.reduce(
    (t, r) => ({ calls: t.calls + r.calls, input: t.input + r.input_tokens, output: t.output + r.output_tokens, cost: t.cost + r.cost_usd }),
    { calls: 0, input: 0, output: 0, cost: 0 },
  );
  const sumSteps = (steps: string[]) =>
    rows.filter((r) => steps.includes(r.step)).reduce((t, r) => ({ calls: t.calls + r.calls, cost: t.cost + r.cost_usd }), { calls: 0, cost: 0 });
  const ingest = sumSteps(["ingest.extract"]);
  const scoring = sumSteps(["match.score"]);
  const answers = sumSteps(["rag.answer"]);
  const askAll = sumSteps(ASK_STEPS);
  const perResume = ingest.calls > 0 ? ingest.cost / ingest.calls : null;
  const shortlistRuns = scoring.calls / CANDIDATES_PER_SHORTLIST;
  const perShortlist = shortlistRuns > 0 ? scoring.cost / shortlistRuns : null;
  const perAnswer = answers.calls > 0 ? askAll.cost / answers.calls : null;

  return (
    <div className="space-y-8">
      {header}

      <section aria-label="Cost summary" className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-5 [&>*:first-child]:col-span-2 [&>*:first-child]:xl:col-span-1">
        <KpiCard
          label="Spent today"
          value={usd(data?.spent_today_usd)}
          caption={data ? `${pct.toFixed(0)}% of the ${formatUsd(data.spend_cap_usd)} daily cap` : ""}
          icon={CalendarClock}
          tone="warning"
          loading={loading}
        >
          {data && (
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(Math.min(100, pct))}
              aria-label={`${pct.toFixed(0)}% of the daily spend cap used`}
              className="h-1.5 overflow-hidden rounded-full bg-muted"
            >
              <div
                className={cn("h-full rounded-full", pct >= 90 ? "bg-danger" : pct >= 70 ? "bg-warning" : "bg-brand")}
                style={{ width: `${Math.min(100, pct)}%` }}
              />
            </div>
          )}
        </KpiCard>
        <KpiCard label="All time" value={usd(totals.cost)} caption={`${formatNumber(totals.calls)} model calls logged`} icon={Wallet} loading={loading} />
        <KpiCard
          label="Per resume"
          value={usd(perResume)}
          caption={`Extraction cost ÷ ${formatNumber(ingest.calls)} extraction calls`}
          icon={FileText}
          tone="info"
          loading={loading}
        />
        <KpiCard
          label="Per shortlist"
          value={usd(perShortlist)}
          caption={`Approximate: scoring ÷ ~${formatNumber(Math.round(shortlistRuns))} runs of ${CANDIDATES_PER_SHORTLIST} candidates`}
          icon={ListChecks}
          tone="success"
          loading={loading}
        />
        <KpiCard
          label="Per Ask answer"
          value={usd(perAnswer)}
          caption={`Route + understand + answer ÷ ${formatNumber(answers.calls)} answers`}
          icon={MessageSquareText}
          tone="tamper"
          loading={loading}
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Cost by day</CardTitle>
            <CardDescription>All model and embedding calls, in USD.</CardDescription>
          </CardHeader>
          <CardContent>
            {!data ? <Skeleton className="h-64" /> : data.by_day.length ? <ByDayChart days={data.by_day} /> : <p className="text-sm text-muted-foreground">No calls yet.</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center gap-3">
            <IconTile icon={ShieldCheck} tone="success" size="sm" />
            <div className="space-y-0.5">
              <CardTitle>How costs are controlled</CardTitle>
              <CardDescription>Built in, not left to discipline.</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3.5">
              {CONTROLS.map((c) => (
                <li key={c.title} className="flex gap-3">
                  <c.icon className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{c.title}</p>
                    <p className="text-xs leading-relaxed text-muted-foreground">{c.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card className="gap-0 overflow-hidden pb-0">
        <CardHeader className="pb-4">
          <CardTitle>By step and model</CardTitle>
          <CardDescription>Where the spend goes, with token counts.</CardDescription>
        </CardHeader>
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent">
              {["Step", "Model", "Calls", "Input tokens", "Output tokens", "Cost"].map((h, i) => (
                <TableHead
                  key={h}
                  className={cn("h-10 px-4 text-xs font-medium tracking-wide text-muted-foreground uppercase", i >= 2 && "text-right", (i === 3 || i === 4) && "hidden md:table-cell", i === 1 && "hidden sm:table-cell")}
                >
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {!data &&
              Array.from({ length: 4 }, (_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={6} className="px-4">
                    <Skeleton className="h-6" />
                  </TableCell>
                </TableRow>
              ))}
            {rows.map((r) => (
              <TableRow key={`${r.step}-${r.model}`}>
                <TableCell className="px-4 font-medium whitespace-normal">
                  {stepLabel(r.step)}
                  <span className="block font-mono text-[11px] font-normal text-muted-foreground">{r.step}</span>
                  <span className={cn("mt-1 inline-flex rounded-md px-1.5 py-0.5 font-mono text-[11px] font-medium ring-1 ring-inset sm:hidden", modelChip(r.model))}>{r.model}</span>
                </TableCell>
                <TableCell className="hidden px-4 sm:table-cell">
                  <span className={cn("inline-flex rounded-md px-1.5 py-0.5 font-mono text-[11px] font-medium ring-1 ring-inset", modelChip(r.model))}>{r.model}</span>
                </TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatNumber(r.calls)}</TableCell>
                <TableCell className="hidden px-4 text-right tabular-nums md:table-cell">{formatNumber(r.input_tokens)}</TableCell>
                <TableCell className="hidden px-4 text-right tabular-nums md:table-cell">{formatNumber(r.output_tokens)}</TableCell>
                <TableCell className="px-4 text-right font-medium tabular-nums">{usd(r.cost_usd)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          {rows.length > 1 && (
            <TableFooter>
              <TableRow>
                <TableCell className="px-4 sm:hidden">Total</TableCell>
                <TableCell className="hidden px-4 sm:table-cell" colSpan={2}>
                  Total
                </TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatNumber(totals.calls)}</TableCell>
                <TableCell className="hidden px-4 text-right tabular-nums md:table-cell">{formatNumber(totals.input)}</TableCell>
                <TableCell className="hidden px-4 text-right tabular-nums md:table-cell">{formatNumber(totals.output)}</TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatUsd(totals.cost)}</TableCell>
              </TableRow>
            </TableFooter>
          )}
        </Table>
      </Card>
    </div>
  );
}
