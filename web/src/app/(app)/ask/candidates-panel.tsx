"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDown, FileText, Loader2, UserRound, Users, X } from "lucide-react";
import { qualityStyle } from "@/components/quality-badge";
import { Button } from "@/components/ui/button";
import { apiFetch, type AskCandidate, type CandidateDetail, type Citation, type ConversationResponse } from "@/lib/api";
import { formatYears, licenseLabel, qualityLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import { avatarTint, cleanSnippet, initials, placeLabel, sectionLabel } from "./lib";

export type OpenResume = (target: { name: string; resumeFileId: number; subtitle?: string }) => void;

/** The right column: candidates behind the selected answer, cited ones first. */
export function CandidatesPanel({
  response,
  onOpenResume,
  onClose,
}: {
  response: ConversationResponse | null;
  onOpenResume: OpenResume;
  /** Shown as a close button in the drawer and sheet variants. */
  onClose?: () => void;
}) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const candidates = response?.candidates ?? [];
  const citations = response?.citations ?? [];
  const byPerson = new Map<number, Citation[]>();
  for (const c of citations) byPerson.set(c.person_id, [...(byPerson.get(c.person_id) ?? []), c]);
  // Cited candidates in the order the answer cites them, then the rest in search order.
  const order = [...byPerson.keys()];
  const cited = candidates.filter((c) => byPerson.has(c.person_id)).sort((a, b) => order.indexOf(a.person_id) - order.indexOf(b.person_id));
  const others = candidates.filter((c) => !byPerson.has(c.person_id));
  const source = response?.standalone_question || response?.question;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start gap-2 border-b px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            Candidates
            {candidates.length > 0 && (
              <span className="rounded-full bg-muted px-1.5 text-[11px] font-medium text-muted-foreground tabular-nums">{candidates.length}</span>
            )}
          </h2>
          {source && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground" title={source}>
              from: {source}
            </p>
          )}
        </div>
        {onClose && (
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close candidates" className="-mr-1 text-muted-foreground">
            <X aria-hidden="true" />
          </Button>
        )}
      </div>

      <div className="relative min-h-0 flex-1 overflow-y-auto p-3">
        {candidates.length === 0 ? (
          <div className="flex h-full min-h-48 flex-col items-center justify-center gap-3 px-6 text-center">
            <span className="flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
              <Users className="size-5" aria-hidden="true" />
            </span>
            <p className="max-w-56 text-sm text-muted-foreground">Candidates from your answers will appear here.</p>
          </div>
        ) : (
          <div className="space-y-5">
            {cited.length > 0 && (
              <Group label="Cited in the answer" count={cited.length}>
                {cited.map((c) => (
                  <CandidateCard
                    key={c.person_id}
                    c={c}
                    quotes={byPerson.get(c.person_id) ?? []}
                    expanded={expanded === c.person_id}
                    onToggle={() => setExpanded((e) => (e === c.person_id ? null : c.person_id))}
                    onOpenResume={onOpenResume}
                  />
                ))}
              </Group>
            )}
            {others.length > 0 && (
              <Group label="Also found" count={others.length}>
                {others.map((c) => (
                  <CandidateCard
                    key={c.person_id}
                    c={c}
                    quotes={[]}
                    expanded={expanded === c.person_id}
                    onToggle={() => setExpanded((e) => (e === c.person_id ? null : c.person_id))}
                    onOpenResume={onOpenResume}
                  />
                ))}
              </Group>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Group({ label, count, children }: { label: string; count: number; children: React.ReactNode }) {
  return (
    <section aria-label={label}>
      <h3 className="mb-2 flex items-center gap-1.5 px-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        {label} <span className="tabular-nums">· {count}</span>
      </h3>
      <ul className="space-y-2">{children}</ul>
    </section>
  );
}

function Quote({ c }: { c: Citation }) {
  return (
    <blockquote className="rounded-md border-l-2 border-brand/50 bg-muted/50 py-1.5 pr-2 pl-2.5 text-xs leading-5 text-foreground/80">
      &ldquo;{c.quote}&rdquo;
      <span className="mt-0.5 block text-[11px] text-muted-foreground not-italic">{sectionLabel(c.section)}</span>
    </blockquote>
  );
}

function CandidateCard({
  c,
  quotes,
  expanded,
  onToggle,
  onOpenResume,
}: {
  c: AskCandidate;
  quotes: Citation[];
  expanded: boolean;
  onToggle: () => void;
  onOpenResume: OpenResume;
}) {
  const router = useRouter();
  const [opening, setOpening] = useState(false);
  const meta = [placeLabel(c.city, c.metro), c.years_experience !== null ? formatYears(c.years_experience) : null].filter(Boolean).join(" · ");
  const q = qualityStyle(c.quality);
  const shown = expanded ? quotes : quotes.slice(0, 2);
  const detailsId = `cand-${c.person_id}-details`;

  async function openResume() {
    const first = quotes[0];
    if (first) {
      onOpenResume({ name: c.full_name, resumeFileId: first.resume_file_id, subtitle: `${sectionLabel(first.section)}: “${first.quote}”` });
      return;
    }
    // Candidates the answer didn't cite carry no file id: look up their current resume.
    setOpening(true);
    try {
      const d = await apiFetch<CandidateDetail>(`/api/candidates/${c.person_id}`);
      onOpenResume({ name: c.full_name, resumeFileId: d.resume_file_id });
    } catch {
      router.push(`/candidates/${c.person_id}`);
    } finally {
      setOpening(false);
    }
  }

  return (
    <li
      className={cn(
        "rounded-xl border bg-card shadow-xs transition-[border-color,box-shadow]",
        expanded ? "border-brand/40 shadow-sm ring-1 ring-brand/15" : "hover:border-foreground/15",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls={detailsId}
        className="flex w-full items-start gap-3 rounded-xl p-3 pb-2 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold", avatarTint(c.person_id))} aria-hidden="true">
          {initials(c.full_name)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <span className="truncate text-sm font-semibold">{c.full_name}</span>
            <span className={cn("size-1.5 shrink-0 rounded-full", q.dot)} title={qualityLabel(c.quality)} aria-hidden="true" />
            <span className="sr-only">, resume quality: {qualityLabel(c.quality)}</span>
          </span>
          {c.headline && <span className="block truncate text-xs text-muted-foreground">{c.headline}</span>}
          {meta && <span className="mt-0.5 block truncate text-xs text-muted-foreground">{meta}</span>}
        </span>
        <ChevronDown className={cn("mt-1 size-4 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-180")} aria-hidden="true" />
      </button>

      <div className="space-y-2 px-3 pb-3" id={detailsId}>
        {c.license_codes.length > 0 && (
          <div className="flex flex-wrap gap-1 pl-12">
            {c.license_codes.map((code) => (
              <span key={code} className="rounded border px-1.5 text-[11px] leading-5 text-foreground/80">
                {licenseLabel(code)}
              </span>
            ))}
          </div>
        )}
        {shown.length > 0 && (
          <div className="space-y-1.5">
            {shown.map((qt, i) => (
              <Quote key={`${qt.chunk_id}-${i}`} c={qt} />
            ))}
          </div>
        )}
        {expanded && c.top_sections.length > 0 && (
          <div className="space-y-1.5 pt-1">
            <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">Matching resume sections</p>
            {c.top_sections.map((s) => (
              <div key={s.chunk_id} className="rounded-md border bg-background/60 p-2 text-xs leading-5">
                <span className="mb-0.5 block text-[11px] font-medium text-muted-foreground">{sectionLabel(s.section)}</span>
                <span className="line-clamp-5 text-foreground/80">{cleanSnippet(s.content)}</span>
              </div>
            ))}
          </div>
        )}
        <div className="flex items-center gap-1.5 pt-0.5">
          <Button variant="outline" size="xs" onClick={openResume} disabled={opening} className="gap-1">
            {opening ? <Loader2 className="animate-spin" aria-hidden="true" /> : <FileText aria-hidden="true" />} Resume
          </Button>
          <Button variant="ghost" size="xs" asChild className="gap-1">
            <Link href={`/candidates/${c.person_id}`}>
              <UserRound aria-hidden="true" /> Profile
            </Link>
          </Button>
          {!expanded && quotes.length > 2 && (
            <button type="button" onClick={onToggle} className="ml-auto rounded-sm text-[11px] text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50">
              +{quotes.length - 2} more quotes
            </button>
          )}
        </div>
      </div>
    </li>
  );
}
