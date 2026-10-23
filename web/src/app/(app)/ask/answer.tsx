"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Loader2, Search } from "lucide-react";
import { QualityBadge } from "@/components/quality-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useUser } from "@/components/auth/user-provider";
import type { AskCandidate, AskResponse, Citation } from "@/lib/api";
import { disciplineLabel, formatUsd, formatYears, humanize, licenseLabel, qualityLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

// Resume section names from the search index → recruiter wording.
const SECTION_LABELS: Record<string, string> = {
  job: "Work history",
  jobs: "Work history",
  summary: "Summary",
  credentials: "Licenses & certifications",
  skills: "Skills",
  education: "Education",
};

export function sectionLabel(section: string): string {
  return SECTION_LABELS[section] ?? humanize(section);
}

/** "Austin · Austin" → "Austin": the metro is only worth showing when it adds something. */
function placeLabel(city: string | null, metro: string | null): string {
  return [city, metro && metro !== city ? metro : null].filter(Boolean).join(" · ");
}

// Rough timings of the RAG graph (~10–15 s total), used to narrate progress while waiting.
const STAGES = [
  { label: "Understanding your question", at: 0 },
  { label: "Searching resumes", at: 2500 },
  { label: "Ranking candidates", at: 5500 },
  { label: "Writing the answer", at: 8000 },
];

// Most non-search replies (greetings, help) come back well within this, so show a light
// "Thinking…" first and only switch to the search stages if the wait gets longer.
const THINKING_MS = 1500;

/** Plan filters → readable chips, e.g. {license_codes:["PE:TX"], min_years: 8} → "PE · TX", "8+ yrs". */
function filterChips(filters: Record<string, unknown>): string[] {
  const chips: string[] = [];
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value === null || value === undefined || value === "" || value === false) continue;
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      chips.push(...value.map((v) => (key.includes("license") ? licenseLabel(String(v)) : humanize(String(v)))));
    } else if (key === "min_years") chips.push(`${value}+ yrs`);
    else if (key === "discipline") chips.push(disciplineLabel(String(value)));
    else if (key === "metro") chips.push(String(value));
    else if (value === true) chips.push(humanize(key));
    else chips.push(key === "quality" ? qualityLabel(String(value)) : String(value));
  }
  return chips;
}

const md: Components = {
  p: ({ children }) => <p className="leading-relaxed [&:not(:first-child)]:mt-3">{children}</p>,
  ul: ({ children }) => <ul className="mt-3 list-disc space-y-1.5 pl-5 marker:text-muted-foreground/60">{children}</ul>,
  ol: ({ children }) => <ol className="mt-3 list-decimal space-y-1.5 pl-5 marker:text-muted-foreground">{children}</ol>,
  li: ({ children }) => <li className="pl-1 leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  h1: ({ children }) => <h3 className="mt-4 text-base font-semibold first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-4 text-base font-semibold first:mt-0">{children}</h3>,
  h3: ({ children }) => <h4 className="mt-4 text-sm font-semibold first:mt-0">{children}</h4>,
  // Answers are model output over untrusted resume text: only allow same-site links, render others as text.
  a: ({ href, children }) =>
    href && href.startsWith("/") && !href.startsWith("//") ? (
      <a href={href} className="font-medium text-brand underline-offset-2 hover:underline">
        {children}
      </a>
    ) : (
      <span>{children}</span>
    ),
  code: ({ children }) => <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{children}</code>,
  blockquote: ({ children }) => <blockquote className="mt-3 border-l-2 pl-3 text-muted-foreground italic">{children}</blockquote>,
  table: ({ children }) => (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-left text-sm [&_td]:border-t [&_td]:px-2 [&_td]:py-1.5 [&_th]:px-2 [&_th]:py-1.5 [&_th]:font-medium">{children}</table>
    </div>
  ),
};

/** Assistant Markdown: no images (an injected resume could make the browser fetch an attacker URL), same-site links only. */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={md} disallowedElements={["img"]} unwrapDisallowed>
        {children}
      </ReactMarkdown>
    </div>
  );
}

/** Pending assistant reply: "Thinking…" briefly, then the staged search progress. */
export function PendingReply() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => setElapsed(Date.now() - start), 250);
    return () => clearInterval(t);
  }, []);

  if (elapsed < THINKING_MS) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status" aria-live="polite">
        <Loader2 className="size-4 animate-spin text-brand" aria-hidden="true" /> Thinking…
      </p>
    );
  }
  const searchElapsed = elapsed - THINKING_MS;
  const current = STAGES.reduce((idx, s, i) => (searchElapsed >= s.at ? i : idx), 0);
  return (
    <div className="space-y-2" role="status" aria-live="polite" aria-label={`${STAGES[current].label}…`}>
      {STAGES.map((s, i) => (
        <div key={s.label} className={cn("flex items-center gap-2 text-sm", i > current && "text-muted-foreground/60")}>
          <span className="flex size-4 items-center justify-center">
            {i < current ? (
              <Check className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            ) : i === current ? (
              <Loader2 className="size-4 animate-spin text-brand" aria-hidden="true" />
            ) : (
              <span className="size-1.5 rounded-full bg-muted-foreground/40" aria-hidden="true" />
            )}
          </span>
          <span className={cn(i === current && "font-medium")}>
            {s.label}
            {i === current && "…"}
          </span>
        </div>
      ))}
      <p className="pt-1 text-xs text-muted-foreground tabular-nums">{(elapsed / 1000).toFixed(0)} s · usually 10–15 s</p>
    </div>
  );
}

function CandidateCard({ c, cited }: { c: AskCandidate; cited: boolean }) {
  return (
    <li className={cn("flex flex-col gap-2 rounded-lg border bg-card p-3", cited && "border-brand/40")}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <Link href={`/candidates/${c.person_id}`} className="text-sm font-medium hover:underline">
              {c.full_name}
            </Link>
            {cited && <Badge className="h-4 bg-brand-soft px-1.5 text-[10px] text-brand">Cited</Badge>}
          </div>
          <p className="line-clamp-1 text-xs text-muted-foreground">{c.headline ?? disciplineLabel(c.discipline)}</p>
        </div>
        <QualityBadge quality={c.quality} short className="shrink-0" />
      </div>
      <p className="text-xs text-muted-foreground">
        {[placeLabel(c.city, c.metro), c.years_experience !== null ? formatYears(c.years_experience) : null].filter(Boolean).join(" · ")}
      </p>
      <div className="flex flex-wrap items-center gap-1">
        {c.license_codes.map((code) => (
          <Badge key={code} variant="outline" className="font-normal">
            {licenseLabel(code)}
          </Badge>
        ))}
        <Button variant="ghost" size="xs" asChild className="ml-auto">
          <Link href={`/candidates/${c.person_id}`}>View</Link>
        </Button>
      </div>
    </li>
  );
}

/** A search answer: the text, "How I searched", verified sources and the candidate cards. */
export function Answer({ text, r, onCite }: { text: string; r: AskResponse; onCite: (c: Citation) => void }) {
  const { user } = useUser();
  const isAdmin = user?.role === "admin";
  const chips = filterChips(r.plan?.filters ?? {});
  const citations = r.citations ?? [];
  const candidates = r.candidates ?? [];
  const dropped = r.dropped_citations ?? [];
  const citedIds = new Set(citations.map((c) => c.person_id));
  const cited = candidates.filter((c) => citedIds.has(c.person_id));
  const others = candidates.filter((c) => !citedIds.has(c.person_id));
  return (
    <div className="space-y-5">
      <Markdown>{text || r.answer}</Markdown>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border bg-muted/30 px-3 py-2 text-xs">
        <span className="flex items-center gap-1.5 font-medium text-muted-foreground">
          <Search className="size-3.5" aria-hidden="true" /> How I searched
        </span>
        {chips.map((c) => (
          <Badge key={c} variant="outline" className="bg-background font-normal">
            {c}
          </Badge>
        ))}
        {r.plan?.search_query && <span className="min-w-0 text-muted-foreground italic">&ldquo;{r.plan.search_query}&rdquo;</span>}
        {isAdmin && (
          <span className="ml-auto text-muted-foreground tabular-nums">
            {[
              r.timings_ms?.total_ms ? `${(r.timings_ms.total_ms / 1000).toFixed(1)} s` : null,
              r.cost_usd !== undefined && r.cost_usd !== null ? formatUsd(r.cost_usd, 3) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
        )}
      </div>

      {citations.length > 0 && (
        <section aria-label="Citations" className="space-y-2">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Sources</h3>
          <ol className="space-y-1.5">
            {citations.map((c, i) => (
              <li key={`${c.chunk_id}-${i}`} className="flex gap-2.5">
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded bg-muted text-[11px] font-medium tabular-nums">
                  {i + 1}
                </span>
                <div className="min-w-0 text-sm">
                  <button
                    type="button"
                    onClick={() => onCite(c)}
                    className="font-medium hover:underline focus-visible:underline focus-visible:outline-none"
                    aria-label={`Open resume of ${c.candidate_name}, ${c.section}`}
                  >
                    {c.candidate_name}
                  </button>
                  <span className="text-muted-foreground"> · {sectionLabel(c.section)} · </span>
                  <Link href={`/candidates/${c.person_id}`} className="text-xs text-brand hover:underline">
                    Profile
                  </Link>
                  <p className="mt-0.5 border-l-2 pl-2.5 text-muted-foreground italic">&ldquo;{c.quote}&rdquo;</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {dropped.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {dropped.length} quote{dropped.length > 1 ? "s" : ""} couldn&apos;t be found in the resumes and {dropped.length > 1 ? "were" : "was"} removed.
        </p>
      )}

      {cited.length > 0 && (
        <section aria-label="Candidates cited in the answer" className="space-y-2">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Cited in the answer ({cited.length})</h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {cited.map((c) => (
              <CandidateCard key={c.person_id} c={c} cited />
            ))}
          </ul>
        </section>
      )}

      {others.length > 0 && (
        <section aria-label="Other candidates the search found" className="space-y-2">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Other candidates the search found ({others.length})
          </h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {others.map((c) => (
              <CandidateCard key={c.person_id} c={c} cited={false} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
