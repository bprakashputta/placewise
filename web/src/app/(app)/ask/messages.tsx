"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowRight, Briefcase, Check, ChevronRight, CircleAlert, FileText, Loader2, RotateCcw, Search, Sparkles, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useUser } from "@/components/auth/user-provider";
import type { Citation, ConversationResponse } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { cn } from "@/lib/utils";
import { BRAND_SOLID, citedPeople, filterChips, jobOrderCode, searchResponse, sectionLabel, type UIMessage } from "./lib";

const md: Components = {
  p: ({ children }) => <p className="leading-7 [&:not(:first-child)]:mt-3">{children}</p>,
  ul: ({ children }) => <ul className="mt-3 list-disc space-y-2 pl-5 marker:text-muted-foreground/50">{children}</ul>,
  ol: ({ children }) => <ol className="mt-3 list-decimal space-y-2 pl-5 marker:text-muted-foreground">{children}</ol>,
  li: ({ children }) => <li className="pl-1 leading-7 [&>ul]:mt-1.5 [&>ol]:mt-1.5">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  h1: ({ children }) => <h3 className="mt-5 text-base font-semibold first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-5 text-base font-semibold first:mt-0">{children}</h3>,
  h3: ({ children }) => <h4 className="mt-4 text-[15px] font-semibold first:mt-0">{children}</h4>,
  // Answers are model output over untrusted resume text: only same-site links, everything else as text.
  a: ({ href, children }) =>
    href && href.startsWith("/") && !href.startsWith("//") ? (
      <a href={href} className="font-medium text-brand underline decoration-brand/30 underline-offset-2 hover:decoration-brand">
        {children}
      </a>
    ) : (
      <span>{children}</span>
    ),
  code: ({ children }) => <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{children}</code>,
  blockquote: ({ children }) => <blockquote className="mt-3 border-l-2 border-brand/40 pl-3 text-muted-foreground">{children}</blockquote>,
  hr: () => <hr className="my-4 border-border" />,
  table: ({ children }) => (
    <div className="mt-3 overflow-x-auto rounded-lg border">
      <table className="w-full text-left text-sm [&_td]:border-t [&_td]:px-3 [&_td]:py-2 [&_th]:bg-muted/50 [&_th]:px-3 [&_th]:py-2 [&_th]:font-medium">
        {children}
      </table>
    </div>
  ),
};

/** Assistant Markdown: no raw HTML, no images (an injected resume could make the browser fetch an attacker URL), same-site links only. */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-[15px] text-foreground/90">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={md} disallowedElements={["img"]} unwrapDisallowed>
        {children}
      </ReactMarkdown>
    </div>
  );
}

export function AssistantAvatar() {
  return (
    <span
      className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand to-fuchsia-500 text-white shadow-sm ring-1 ring-black/5"
      aria-hidden="true"
    >
      <Sparkles className="size-3.5" />
    </span>
  );
}

function AssistantShell({ children, label = "Placewise" }: { children: React.ReactNode; label?: string }) {
  return (
    <div className="flex items-start gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1">
        <span className="sr-only">{label}:</span>
        {children}
      </div>
    </div>
  );
}

export function UserMessage({ m, pending, onRetry }: { m: UIMessage; pending: boolean; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-end gap-2">
      <span className="sr-only">You:</span>
      <p
        className={cn(
          "max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-[15px] leading-6 break-words whitespace-pre-wrap shadow-sm",
          BRAND_SOLID,
          m.failed && "opacity-70",
        )}
      >
        {m.content}
      </p>
      {m.failed && (
        <div role="alert" className="flex max-w-[85%] items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div className="space-y-2">
            <p>Not sent. {m.failed}</p>
            <Button variant="outline" size="xs" onClick={onRetry} disabled={pending} className="gap-1">
              <RotateCcw aria-hidden="true" /> Try again
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function HowISearched({ r, isAdmin }: { r: ConversationResponse; isAdmin: boolean }) {
  const chips = filterChips(r.plan?.filters ?? {});
  const meta = isAdmin
    ? [
        r.timings_ms?.total_ms ? `${(r.timings_ms.total_ms / 1000).toFixed(1)} s` : null,
        r.cost_usd !== undefined && r.cost_usd !== null ? formatUsd(r.cost_usd, 3) : null,
      ].filter(Boolean)
    : [];
  if (chips.length === 0 && !r.plan?.search_query && meta.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs text-muted-foreground">
      <span className="flex items-center gap-1 font-medium">
        <Search className="size-3" aria-hidden="true" /> How I searched
      </span>
      {chips.map((c) => (
        <span key={c} className="rounded-md border bg-muted/40 px-1.5 py-0.5 text-[11px] text-foreground/80">
          {c}
        </span>
      ))}
      {r.plan?.search_query && <span className="min-w-0 italic">&ldquo;{r.plan.search_query}&rdquo;</span>}
      {meta.length > 0 && (
        <span className="ml-auto text-[11px] text-muted-foreground/80 tabular-nums" title="Admin only: time and AI cost">
          {meta.join(" · ")}
        </span>
      )}
    </div>
  );
}

function Sources({ citations, onCite }: { citations: Citation[]; onCite: (c: Citation) => void }) {
  return (
    <Collapsible>
      <CollapsibleTrigger className="group flex items-center gap-1.5 rounded-md text-xs font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50">
        <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" aria-hidden="true" />
        <FileText className="size-3.5" aria-hidden="true" />
        Sources ({citations.length})
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ol className="mt-2 space-y-1 rounded-xl border bg-card p-1.5" aria-label="Sources">
          {citations.map((c, i) => (
            <li key={`${c.chunk_id}-${i}`} className="flex gap-2.5 rounded-lg px-2 py-1.5 hover:bg-muted/50">
              <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md bg-muted text-[11px] font-medium text-muted-foreground tabular-nums">
                {i + 1}
              </span>
              <div className="min-w-0 text-sm">
                <button
                  type="button"
                  onClick={() => onCite(c)}
                  className="rounded-sm font-medium outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
                  aria-label={`Open resume of ${c.candidate_name}, ${sectionLabel(c.section)}`}
                >
                  {c.candidate_name}
                </button>
                <span className="text-xs text-muted-foreground"> · {sectionLabel(c.section)} · </span>
                <Link href={`/candidates/${c.person_id}`} className="rounded-sm text-xs text-brand outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50">
                  Profile
                </Link>
                <p className="mt-0.5 text-[13px] leading-5 text-muted-foreground">&ldquo;{c.quote}&rdquo;</p>
              </div>
            </li>
          ))}
        </ol>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function AssistantMessage({
  m,
  inPanel,
  onShowInPanel,
  onCite,
}: {
  m: UIMessage;
  /** This answer's candidates are the ones in the right panel. */
  inPanel: boolean;
  onShowInPanel: () => void;
  onCite: (c: Citation) => void;
}) {
  const { user } = useUser();
  const r = searchResponse(m);
  const searched = m.kind === "follow_up" ? r?.standalone_question : null;
  const cited = r ? citedPeople(r).length : 0;
  const total = r?.candidates?.length ?? 0;
  const dropped = r?.dropped_citations ?? [];
  const jo = m.kind === "job_order" || m.kind === "intro";
  return (
    <AssistantShell>
      <div className="space-y-3">
        {(m.kind === "job_order" || searched) && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {jo && (
              <span className="inline-flex items-center gap-1 rounded-md border border-brand/25 bg-brand/5 px-1.5 py-0.5 font-medium text-brand">
                <Briefcase className="size-3" aria-hidden="true" /> Job order
              </span>
            )}
            {searched && (
              <span className="min-w-0">
                <span className="font-medium">Searched:</span> <span className="italic">{searched}</span>
              </span>
            )}
          </div>
        )}
        <Markdown>{m.content || r?.answer || ""}</Markdown>
        {r && (
          <div className="space-y-3 pt-1">
            <HowISearched r={r} isAdmin={user?.role === "admin"} />
            {total > 0 && (
              <button
                type="button"
                onClick={onShowInPanel}
                aria-pressed={inPanel}
                className={cn(
                  "group flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-sm shadow-xs outline-none transition-colors hover:border-brand/40 hover:bg-brand-soft/60 focus-visible:ring-3 focus-visible:ring-ring/50",
                  inPanel ? "border-brand/40 bg-brand-soft/60" : "bg-card",
                )}
              >
                <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand">
                  <Users className="size-3.5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="font-medium">
                    {cited > 0 ? `${cited} candidate${cited === 1 ? "" : "s"} cited` : `${total} candidate${total === 1 ? "" : "s"} found`}
                  </span>
                  {cited > 0 && total > cited && <span className="hidden text-muted-foreground sm:inline"> · {total - cited} more found</span>}
                </span>
                <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-brand">
                  View in panel
                  <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                </span>
              </button>
            )}
            {(r.citations?.length ?? 0) > 0 && <Sources citations={r.citations} onCite={onCite} />}
            {dropped.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {dropped.length} quote{dropped.length > 1 ? "s" : ""} couldn&apos;t be found in the resumes and {dropped.length > 1 ? "were" : "was"} removed.
              </p>
            )}
          </div>
        )}
      </div>
    </AssistantShell>
  );
}

// Rough timings of the RAG graph (~10–15 s total), used to narrate progress while waiting.
const STEPS = [
  { label: "Understanding your question", at: 0 },
  { label: "Searching 4,600 resume sections", at: 2000 },
  { label: "Ranking the best matches", at: 4500 },
  { label: "Writing a cited answer", at: 7000 },
];

// Greetings and help come back almost instantly, so start with a light "Thinking…".
const THINKING_MS = 1200;

/** Pending assistant reply: "Thinking…" briefly, then a step timeline. */
export function PendingReply() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => setElapsed(Date.now() - start), 200);
    return () => clearInterval(t);
  }, []);

  // The timeline is taller than "Thinking…": keep it in view when it appears.
  const steps = elapsed >= THINKING_MS;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!steps) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    ref.current?.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  }, [steps]);

  if (!steps) {
    return (
      <AssistantShell>
        <p className="flex h-7 items-center gap-2 text-sm text-muted-foreground" role="status" aria-live="polite">
          <span className="flex gap-1" aria-hidden="true">
            {[0, 150, 300].map((d) => (
              <span key={d} className="size-1.5 rounded-full bg-brand/60 motion-safe:animate-pulse" style={{ animationDelay: `${d}ms` }} />
            ))}
          </span>
          Thinking…
        </p>
      </AssistantShell>
    );
  }
  const t = elapsed - THINKING_MS;
  const current = STEPS.reduce((idx, s, i) => (t >= s.at ? i : idx), 0);
  return (
    <AssistantShell>
      <div ref={ref} className="scroll-mb-4 rounded-xl border bg-card p-3.5 shadow-xs" role="status" aria-live="polite" aria-label={`${STEPS[current].label}…`}>
        <ol className="relative space-y-3">
          {STEPS.map((s, i) => {
            const done = i < current;
            const active = i === current;
            return (
              <li key={s.label} className="relative flex items-center gap-3 text-sm">
                {i < STEPS.length - 1 && (
                  <span
                    className={cn("absolute top-5 left-[9px] h-3 w-px", done ? "bg-emerald-500/50" : "bg-border")}
                    aria-hidden="true"
                  />
                )}
                <span
                  className={cn(
                    "flex size-[19px] shrink-0 items-center justify-center rounded-full border transition-colors",
                    done && "border-emerald-500/40 bg-emerald-500/10",
                    active && "border-brand/40 bg-brand/10",
                  )}
                  aria-hidden="true"
                >
                  {done ? (
                    <Check className="size-3 text-emerald-600 dark:text-emerald-400" />
                  ) : active ? (
                    <Loader2 className="size-3 animate-spin text-brand" />
                  ) : (
                    <span className="size-1 rounded-full bg-muted-foreground/40" />
                  )}
                </span>
                <span className={cn(done && "text-muted-foreground", active && "font-medium text-foreground", !done && !active && "text-muted-foreground/70")}>
                  {s.label}
                  {active && "…"}
                </span>
              </li>
            );
          })}
        </ol>
        <p className="mt-3 border-t pt-2.5 text-xs text-muted-foreground tabular-nums">{Math.floor(elapsed / 1000)} s · usually 10–15 s</p>
      </div>
    </AssistantShell>
  );
}

/** Small JO chip used in the header. */
export function JobOrderChip({ id, title }: { id: number; title: string | null }) {
  return (
    <Link
      href={`/job-orders/${id}`}
      title={title ?? undefined}
      className="inline-flex max-w-[16rem] min-w-0 items-center gap-1 rounded-md border border-brand/25 bg-brand/5 px-1.5 py-0.5 text-xs font-medium text-brand outline-none hover:bg-brand/10 focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Briefcase className="size-3 shrink-0" aria-hidden="true" />
      <span className="shrink-0">{jobOrderCode(id)}</span>
      {title && <span className="truncate font-normal text-foreground/70">· {title}</span>}
    </Link>
  );
}
