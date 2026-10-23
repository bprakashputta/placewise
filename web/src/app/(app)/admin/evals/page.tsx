import { FileScan, FlaskConical, Info, Quote, Route, Scale, Search, TestTubes, type LucideIcon } from "lucide-react";
import type { Metadata } from "next";
import { IconTile, PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { EVAL_ANSWER_KEY_NOTE, EVAL_MEASURED, EVAL_RESULTS, type EvalResult } from "../eval-numbers";
import { AblationChart } from "./ablation-chart";

export const metadata: Metadata = { title: "Evals" };

type Tone = "brand" | "info" | "success" | "warning" | "tamper" | "muted";

const LOOK: Record<string, { icon: LucideIcon; tone: Tone }> = {
  ingest: { icon: FileScan, tone: "brand" },
  retrieval: { icon: Search, tone: "info" },
  ask: { icon: Quote, tone: "tamper" },
  matching: { icon: Scale, tone: "warning" },
  routing: { icon: Route, tone: "success" },
  tests: { icon: TestTubes, tone: "muted" },
};

const HEADLINE_TEXT: Record<Tone, string> = {
  brand: "text-brand",
  info: "text-info-strong",
  success: "text-success-strong",
  warning: "text-warning-strong",
  tamper: "text-tamper-strong",
  muted: "text-foreground",
};

function CommandChip({ command }: { command: string }) {
  return (
    <code className="inline-flex max-w-full items-center gap-1.5 overflow-x-auto rounded-md bg-muted px-2 py-1 font-mono text-[11px] whitespace-nowrap text-foreground/85 ring-1 ring-border ring-inset">
      <span className="text-muted-foreground select-none" aria-hidden="true">
        $
      </span>
      {command}
    </code>
  );
}

function EvalCard({ e, className }: { e: EvalResult; className?: string }) {
  const look = LOOK[e.id] ?? { icon: FlaskConical, tone: "brand" as Tone };
  return (
    <Card className={cn("gap-5", className)}>
      <CardHeader className="flex flex-row items-center gap-3">
        <IconTile icon={look.icon} tone={look.tone} />
        <CardTitle className="text-base">{e.title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-5">
        <div>
          <p className={cn("text-4xl leading-none font-semibold tracking-[-0.03em] tabular-nums", HEADLINE_TEXT[look.tone])}>{e.headline.value}</p>
          <p className="mt-1.5 text-sm font-medium">{e.headline.label}</p>
        </div>

        <dl className={cn("grid gap-px overflow-hidden rounded-lg border bg-border", e.metrics.length > 1 && "sm:grid-cols-2")}>
          {e.metrics.map((m) => (
            <div key={m.label} className="bg-card px-3 py-2.5">
              <dt className="sr-only">{m.label}</dt>
              <dd className="text-lg font-semibold tabular-nums">{m.value}</dd>
              <dd className="text-xs leading-snug text-muted-foreground">{m.label}</dd>
            </div>
          ))}
        </dl>

        {e.id === "retrieval" && <AblationChart />}

        <div className="mt-auto space-y-3 border-t pt-4 text-[13px] leading-relaxed">
          <p>
            <span className="font-semibold">What this means: </span>
            <span className="text-muted-foreground">{e.meaning}</span>
          </p>
          <p>
            <span className="font-semibold">How it&apos;s measured: </span>
            <span className="text-muted-foreground">{e.measured}</span>
          </p>
          {e.command && <CommandChip command={e.command} />}
        </div>
      </CardContent>
    </Card>
  );
}

export default function EvalsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        icon={FlaskConical}
        eyebrow="Admin · Measured results"
        title="Evals"
        description={
          <>
            {EVAL_MEASURED}. {EVAL_ANSWER_KEY_NOTE}
          </>
        }
      />

      <div className="flex items-start gap-3 rounded-xl border bg-info-soft/60 px-4 py-3 text-[13px] text-info-strong">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>
          The synthetic generator decides each candidate&apos;s true facts first (licenses, years, fit for every job order), then writes the resumes.
          That answer key is what these evals grade against. These are fixed results from the last run, not live numbers; synthetic resumes are cleaner
          than real ones, so treat them as an optimistic upper bound.
        </p>
      </div>

      <div className="grid items-stretch gap-6 lg:grid-cols-2">
        {EVAL_RESULTS.map((e) => (
          <EvalCard key={e.id} e={e} />
        ))}
      </div>
    </div>
  );
}
