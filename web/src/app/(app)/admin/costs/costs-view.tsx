"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CircleDollarSign } from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { useUser } from "@/components/auth/user-provider";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, useApi, type Costs } from "@/lib/api";
import { formatNumber, formatUsd, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

const STEP_LABELS: Record<string, string> = {
  "rag.answer": "Ask: answer",
  "rag.understand": "Ask: understand question",
  "ingest.extract": "Resume extraction",
  "match.score": "Matching: score candidate",
  "job_order.extract": "Job order: structure notes",
};

function stepLabel(step: string) {
  return STEP_LABELS[step] ?? step.split(".").map(humanize).join(" › ");
}

// A matching run scores up to 12 candidates, one model call each (see the match graph).
const CANDIDATES_PER_SHORTLIST = 12;

function shortDay(day: string) {
  // "2026-10-22" → "Oct 22" (parsed as a calendar date, not shifted by the local timezone)
  const [y, m, d] = day.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

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
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="day"
            tickFormatter={shortDay}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            minTickGap={16}
          />
          <YAxis
            tickFormatter={(v: number) => `$${v}`}
            tickLine={false}
            axisLine={false}
            width={48}
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
          />
          <Tooltip content={<DayTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.6 }} />
          <Bar dataKey="cost_usd" fill="var(--brand)" radius={[4, 4, 0, 0]} maxBarSize={40} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CostsView() {
  const { user } = useUser();
  // Recruiters get the "Admins only" state without a request (the API would answer 403 anyway).
  const isAdmin = user?.role === "admin";
  const api = useApi<Costs>(isAdmin ? "/api/admin/costs" : null);
  const { data, loading, reload } = api;
  const error = user && !isAdmin ? new ApiError(403, "Admins only") : api.error;

  const header = <PageHeader title="AI costs" description="Model and embedding spend per day, step and model." />;

  if (error && error.status !== 404) return <div className="space-y-6">{header}<ApiErrorState error={error} onRetry={reload} /></div>;
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
  const sumStep = (step: string) =>
    rows.filter((r) => r.step === step).reduce((t, r) => ({ calls: t.calls + r.calls, cost: t.cost + r.cost_usd }), { calls: 0, cost: 0 });
  const ingest = sumStep("ingest.extract");
  const scoring = sumStep("match.score");
  const perResume = ingest.calls > 0 ? ingest.cost / ingest.calls : null;
  const shortlistRuns = scoring.calls / CANDIDATES_PER_SHORTLIST;
  const perShortlist = shortlistRuns > 0 ? scoring.cost / shortlistRuns : null;
  const unitCards = [
    {
      label: "Average cost per resume",
      value: perResume,
      note: `Resume extraction cost ÷ ${formatNumber(ingest.calls)} extraction calls.`,
    },
    {
      label: "Average cost per shortlist",
      value: perShortlist,
      note: `Approximate: scoring cost ÷ about ${formatNumber(Math.round(shortlistRuns))} runs (${CANDIDATES_PER_SHORTLIST} candidates scored per run).`,
    },
  ];

  return (
    <div className="space-y-6">
      {header}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Spent today</CardDescription>
            <CardTitle className="text-3xl font-semibold tabular-nums">
              {loading || !data ? <Skeleton className="h-9 w-24" /> : formatUsd(data.spent_today_usd)}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data && (
              <>
                <Progress
                  value={Math.min(100, pct)}
                  aria-label={`${pct.toFixed(0)}% of the daily cap used`}
                  className={cn("h-2", pct >= 90 && "[&>*]:bg-destructive", pct >= 70 && pct < 90 && "[&>*]:bg-amber-500")}
                />
                <p className="text-xs text-muted-foreground">
                  {pct.toFixed(0)}% of the {formatUsd(data.spend_cap_usd)} daily cap. When it&apos;s reached, new AI work pauses until tomorrow instead of failing.
                </p>
              </>
            )}
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Cost by day</CardTitle>
            <CardDescription>All model calls, in USD.</CardDescription>
          </CardHeader>
          <CardContent>
            {!data ? <Skeleton className="h-64" /> : data.by_day.length ? <ByDayChart days={data.by_day} /> : <p className="text-sm text-muted-foreground">No calls yet.</p>}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        {unitCards.map((c) => (
          <Card key={c.label}>
            <CardHeader>
              <CardDescription>{c.label}</CardDescription>
              <CardTitle className="text-3xl font-semibold tabular-nums">
                {!data ? <Skeleton className="h-9 w-24" /> : c.value === null ? "–" : formatUsd(c.value, c.value < 0.1 ? 3 : 2)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{data ? c.note : " "}</p>
            </CardContent>
          </Card>
        ))}
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
                <TableHead key={h} className={cn("h-10 px-4 text-xs font-medium tracking-wide text-muted-foreground uppercase", i >= 2 && "text-right")}>
                  {h}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {!data && (
              <TableRow>
                <TableCell colSpan={6} className="px-4">
                  <Skeleton className="h-16" />
                </TableCell>
              </TableRow>
            )}
            {rows.map((r) => (
              <TableRow key={`${r.step}-${r.model}`}>
                <TableCell className="px-4 font-medium">{stepLabel(r.step)}</TableCell>
                <TableCell className="px-4 font-mono text-xs">{r.model}</TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatNumber(r.calls)}</TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatNumber(r.input_tokens)}</TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatNumber(r.output_tokens)}</TableCell>
                <TableCell className="px-4 text-right font-medium tabular-nums">{formatUsd(r.cost_usd, r.cost_usd > 0 && r.cost_usd < 0.1 ? 3 : 2)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          {rows.length > 1 && (
            <TableFooter>
              <TableRow>
                <TableCell className="px-4" colSpan={2}>
                  Total
                </TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatNumber(totals.calls)}</TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatNumber(totals.input)}</TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatNumber(totals.output)}</TableCell>
                <TableCell className="px-4 text-right tabular-nums">{formatUsd(totals.cost)}</TableCell>
              </TableRow>
            </TableFooter>
          )}
        </Table>
      </Card>
    </div>
  );
}
