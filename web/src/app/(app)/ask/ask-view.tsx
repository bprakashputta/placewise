"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUp, Check, CircleAlert, FileText, Loader2, Search, Sparkles, User } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { QualityBadge } from "@/components/quality-badge";
import { ResumeViewer, type ViewerTarget } from "@/components/resume-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useUser } from "@/components/auth/user-provider";
import { ApiError, apiFetch, type AskCandidate, type AskResponse, type Citation } from "@/lib/api";
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

function sectionLabel(section: string): string {
  return SECTION_LABELS[section] ?? humanize(section);
}

/** "Austin · Austin" → "Austin": the metro is only worth showing when it adds something. */
function placeLabel(city: string | null, metro: string | null): string {
  return [city, metro && metro !== city ? metro : null].filter(Boolean).join(" · ");
}

const EXAMPLES = [
  "Who holds a Texas PE with drainage experience in DFW?",
  "Which licensed architects have healthcare projects over $50M?",
  "Find MEP engineers in Houston who know Revit and are LEED AP.",
];

// Rough timings of the RAG graph (~10–15 s total), used to narrate progress while waiting.
const STAGES = [
  { label: "Understanding your question", at: 0 },
  { label: "Searching resumes", at: 2500 },
  { label: "Ranking candidates", at: 5500 },
  { label: "Writing the answer", at: 8000 },
];

type Turn = {
  id: number;
  question: string;
  response?: AskResponse;
  error?: string;
};

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 429) return "Today's AI spend cap has been reached, so Ask is paused until tomorrow. An admin can raise the cap.";
    if (e.status === 422) return "That question couldn't be processed. Try rephrasing it.";
    return e.message;
  }
  return "Can't reach the server. Check your connection and try again.";
}

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

function PendingStages() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => setElapsed(Date.now() - start), 250);
    return () => clearInterval(t);
  }, []);
  const current = STAGES.reduce((idx, s, i) => (elapsed >= s.at ? i : idx), 0);
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

function Answer({ r, onCite }: { r: AskResponse; onCite: (c: Citation) => void }) {
  const { user } = useUser();
  const isAdmin = user?.role === "admin";
  const chips = filterChips(r.plan?.filters ?? {});
  const citedIds = new Set(r.citations.map((c) => c.person_id));
  const cited = r.candidates.filter((c) => citedIds.has(c.person_id));
  const others = r.candidates.filter((c) => !citedIds.has(c.person_id));
  return (
    <div className="space-y-5">
      <div className="text-sm">
        {/* No images: an injected resume could otherwise make the browser fetch an attacker URL */}
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={md} disallowedElements={["img"]} unwrapDisallowed>
          {r.answer}
        </ReactMarkdown>
      </div>

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
              r.cost_usd !== undefined ? formatUsd(r.cost_usd, 3) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
        )}
      </div>

      {r.citations.length > 0 && (
        <section aria-label="Citations" className="space-y-2">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Sources</h3>
          <ol className="space-y-1.5">
            {r.citations.map((c, i) => (
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

      {r.dropped_citations.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {r.dropped_citations.length} quote{r.dropped_citations.length > 1 ? "s" : ""} couldn&apos;t be found in the resumes and{" "}
          {r.dropped_citations.length > 1 ? "were" : "was"} removed.
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

export function AskView() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const pending = turns.some((t) => !t.response && !t.error);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Bring the newest question into view (its start, so long answers read from the top).
    endRef.current?.parentElement?.querySelector("li[data-turn]:last-child")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [turns]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || pending) return;
    const id = Date.now();
    setTurns((t) => [...t, { id, question: q }]);
    setText("");
    try {
      const response = await apiFetch<AskResponse>("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, response } : x)));
    } catch (e) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: errorMessage(e) } : x)));
    }
    inputRef.current?.focus();
  }

  const onCite = (c: Citation) =>
    setViewer({
      title: c.candidate_name,
      subtitle: `${sectionLabel(c.section)}: “${c.quote}”`,
      viewUrl: `/api/candidates/files/${c.resume_file_id}/view`,
      downloadUrl: `/api/candidates/files/${c.resume_file_id}`,
    });

  return (
    <div className="space-y-6">
      <PageHeader title="Ask" description="Questions about your candidate pool, answered with citations to the resumes." />
      <Card className="flex min-h-[32rem] flex-col gap-0 py-0">
        <CardContent className="flex flex-1 flex-col px-0">
          {turns.length > 0 && <div ref={endRef} className="order-last" />}
          {turns.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 text-center">
              <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
                <Sparkles className="size-5" aria-hidden="true" />
              </div>
              <h2 className="text-sm font-semibold">Ask anything about your candidates</h2>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Every answer links back to the resume lines it came from, and quotes are checked against the resumes.
              </p>
              <ul className="mt-6 flex max-w-2xl flex-wrap justify-center gap-2" aria-label="Example questions">
                {EXAMPLES.map((q) => (
                  <li key={q}>
                    <Button variant="outline" size="sm" onClick={() => ask(q)} className="h-auto rounded-full px-3 py-1.5 text-left whitespace-normal">
                      {q}
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <ol className="flex-1 divide-y" aria-label="Conversation">
              {turns.map((t) => (
                <li key={t.id} data-turn className="scroll-mt-20 space-y-4 px-4 py-5 sm:px-6">
                  <div className="flex items-start gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted">
                      <User className="size-3.5 text-muted-foreground" aria-hidden="true" />
                    </span>
                    <p className="pt-1 text-sm font-medium">{t.question}</p>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
                      <Sparkles className="size-3.5" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1 pt-1">
                      {t.response ? (
                        <Answer r={t.response} onCite={onCite} />
                      ) : t.error ? (
                        <div role="alert" className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                          <div className="space-y-2">
                            <p>{t.error}</p>
                            <Button variant="outline" size="xs" onClick={() => ask(t.question)} disabled={pending}>
                              Try again
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <PendingStages />
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
        <form
          className="sticky bottom-0 flex items-end gap-2 rounded-b-xl border-t bg-card p-3"
          aria-label="Ask a question"
          onSubmit={(e) => {
            e.preventDefault();
            ask(text);
          }}
        >
          <label htmlFor="ask-input" className="sr-only">
            Your question
          </label>
          <textarea
            id="ask-input"
            ref={inputRef}
            value={text}
            rows={1}
            maxLength={1000}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask(text);
              }
            }}
            placeholder={pending ? "Working on your question…" : "Ask about your candidate pool…"}
            className="max-h-40 min-h-9 flex-1 resize-none rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
          />
          <Button type="submit" size="icon-lg" disabled={pending || !text.trim()} aria-label="Send question">
            {pending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <ArrowUp aria-hidden="true" />}
          </Button>
        </form>
      </Card>
      {turns.length > 0 && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <FileText className="size-3.5" aria-hidden="true" /> History lasts for this visit only. Each question costs a few cents of AI usage.
        </p>
      )}
      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
    </div>
  );
}
