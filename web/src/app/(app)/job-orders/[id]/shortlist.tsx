"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  CircleHelp,
  CircleSlash,
  Eye,
  Info,
  ThumbsDown,
  ThumbsUp,
  Undo2,
  UserRound,
  X,
} from "lucide-react";
import { QualityBadge } from "@/components/quality-badge";
import type { ViewerTarget } from "@/components/resume-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { apiFetch } from "@/lib/api";
import { cleanRequirement, formatYears, licenseLabel } from "@/lib/format";
import type { Match, MatchDecision, Verdict } from "@/lib/job-types";
import { cn } from "@/lib/utils";

const REC_STYLES: Record<Match["recommendation"], { label: string; className: string }> = {
  submit: { label: "Submit", className: "bg-emerald-500/10 text-emerald-700 ring-emerald-600/20 dark:text-emerald-300 dark:ring-emerald-400/25" },
  consider: { label: "Consider", className: "bg-amber-500/10 text-amber-800 ring-amber-600/25 dark:text-amber-300 dark:ring-amber-400/25" },
  pass: { label: "Pass", className: "bg-muted text-muted-foreground ring-border" },
};

const VERDICTS: Record<Verdict["verdict"], { icon: typeof Check; label: string; className: string }> = {
  met: { icon: Check, label: "Met", className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  partial: { icon: CircleSlash, label: "Partly met", className: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  not_met: { icon: X, label: "Not met", className: "bg-red-500/15 text-red-700 dark:text-red-300" },
  unknown: { icon: CircleHelp, label: "Unknown", className: "bg-muted text-muted-foreground" },
};

type Counts = Partial<Record<Verdict["verdict"], number>>;

function countVerdicts(verdicts: Verdict[]): Counts {
  return verdicts.reduce<Counts>((acc, v) => ({ ...acc, [v.verdict]: (acc[v.verdict] ?? 0) + 1 }), {});
}

/** "Computed from the 7 requirements: 6 met, 1 partly met. Must-haves count 3×." */
function scoreExplanation(total: number, counts: Counts): string {
  const parts = [
    counts.met && `${counts.met} met`,
    counts.partial && `${counts.partial} partly met`,
    counts.not_met && `${counts.not_met} not met`,
    counts.unknown && `${counts.unknown} unknown`,
  ].filter(Boolean);
  return `Computed from the ${total} requirement${total === 1 ? "" : "s"}: ${parts.join(", ") || "none judged"}. Must-haves count 3×.`;
}

/** 0–100 score as a ring; color by band so it reads at a glance, number always printed. */
function ScoreRing({ score, explanation }: { score: number; explanation: string }) {
  const r = 20;
  const c = 2 * Math.PI * r;
  const color = score >= 80 ? "text-emerald-500" : score >= 60 ? "text-amber-500" : "text-muted-foreground";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          className="relative size-14 shrink-0 cursor-help rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          role="img"
          tabIndex={0}
          aria-label={`Score ${Math.round(score)} out of 100. ${explanation}`}
        >
          <svg viewBox="0 0 48 48" className="size-full -rotate-90">
            <circle cx="24" cy="24" r={r} fill="none" strokeWidth="4" className="stroke-muted" />
            <circle
              cx="24"
              cy="24"
              r={r}
              fill="none"
              strokeWidth="4"
              strokeLinecap="round"
              stroke="currentColor"
              className={color}
              strokeDasharray={c}
              strokeDashoffset={c * (1 - Math.max(0, Math.min(100, score)) / 100)}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold tabular-nums">{Math.round(score)}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent className="max-w-64">{explanation}</TooltipContent>
    </Tooltip>
  );
}

function VerdictRow({ v }: { v: Verdict }) {
  const s = VERDICTS[v.verdict] ?? VERDICTS.unknown;
  return (
    <li className="flex gap-3 py-2.5">
      <span className={cn("mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full", s.className)} title={s.label}>
        <s.icon className="size-3" aria-hidden="true" />
        <span className="sr-only">{s.label}:</span>
      </span>
      <div className="min-w-0 space-y-1 text-sm">
        <p className="font-medium">{cleanRequirement(v.requirement)}</p>
        {v.evidence && (
          <p className="border-l-2 pl-2.5 text-muted-foreground italic">
            <span className="text-[11px] font-medium tracking-wide not-italic uppercase">From the resume: </span>&ldquo;{v.evidence}&rdquo;
          </p>
        )}
        {v.note && <p className="text-xs text-muted-foreground">{v.note}</p>}
      </div>
    </li>
  );
}

/** Inline gaps next to "6/7 met": "Missing: PMP · Partly: DFW based". */
function Gaps({ verdicts }: { verdicts: Verdict[] }) {
  const missing = verdicts.filter((v) => v.verdict === "not_met").map((v) => cleanRequirement(v.requirement));
  const partly = verdicts.filter((v) => v.verdict === "partial").map((v) => cleanRequirement(v.requirement));
  const unknown = verdicts.filter((v) => v.verdict === "unknown").map((v) => cleanRequirement(v.requirement));
  if (!missing.length && !partly.length && !unknown.length) return null;
  return (
    <p className="text-xs text-muted-foreground">
      {[
        missing.length > 0 && (
          <span key="m">
            <span className="font-medium text-red-700 dark:text-red-300">Missing:</span> {missing.join(", ")}
          </span>
        ),
        partly.length > 0 && (
          <span key="p">
            <span className="font-medium text-amber-700 dark:text-amber-300">Partly:</span> {partly.join(", ")}
          </span>
        ),
        unknown.length > 0 && (
          <span key="u">
            <span className="font-medium">Unclear:</span> {unknown.join(", ")}
          </span>
        ),
      ]
        .filter(Boolean)
        .map((el, i) => (
          <span key={i}>
            {i > 0 && " · "}
            {el}
          </span>
        ))}
    </p>
  );
}

function MatchCard({
  m,
  rank,
  status,
  onDecide,
  onViewResume,
}: {
  m: Match;
  rank: number;
  status: MatchDecision;
  onDecide: (s: MatchDecision) => void;
  onViewResume: () => void;
}) {
  const [open, setOpen] = useState(false);
  const rec = REC_STYLES[m.recommendation] ?? REC_STYLES.pass;
  const counts = countVerdicts(m.verdicts);
  const score = Math.round(m.score);
  const flagsLabel = `${m.flags.length} flag${m.flags.length === 1 ? "" : "s"} to check`;
  return (
    <li
      className={cn(
        "rounded-xl border bg-card transition-colors",
        status === "approved" && "border-emerald-500/40",
        status === "rejected" && "opacity-70",
      )}
    >
      <div className="flex gap-4 p-4">
        <div className="flex flex-col items-center gap-1">
          <ScoreRing score={m.score} explanation={scoreExplanation(m.verdicts.length, counts)} />
          <span className="text-[11px] text-muted-foreground tabular-nums">#{rank}</span>
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Link href={`/candidates/${m.person_id}`} className="font-medium hover:underline">
                  {m.full_name}
                </Link>
                <Badge className={cn("ring-1 ring-inset", rec.className)}>
                  <span className="font-normal opacity-80">Suggested:</span> {rec.label}
                </Badge>
                {status !== "proposed" && (
                  <Badge variant={status === "approved" ? "default" : "secondary"} className="capitalize">
                    {status === "approved" ? <ThumbsUp aria-hidden="true" /> : <ThumbsDown aria-hidden="true" />}
                    {status}
                  </Badge>
                )}
              </div>
              <p className="line-clamp-1 text-sm text-muted-foreground">{m.headline ?? "–"}</p>
            </div>
            <QualityBadge quality={m.quality} short />
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
            {m.metro && <span>{m.metro}</span>}
            {m.years_experience !== null && <span>{formatYears(m.years_experience)}</span>}
            <span className="flex flex-wrap gap-1">
              {m.license_codes.map((c) => (
                <Badge key={c} variant="outline" className="font-normal">
                  {licenseLabel(c)}
                </Badge>
              ))}
            </span>
          </div>
          {m.summary && <p className="text-sm leading-relaxed">{m.summary}</p>}
          {m.flags.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
                {score === 100 ? `100 · ${flagsLabel}` : flagsLabel}
              </p>
              <ul className="space-y-1" aria-label="Flags to check">
                {m.flags.map((f) => (
                  <li key={f} className="flex gap-2 rounded-md bg-amber-500/10 px-2.5 py-1.5 text-xs text-amber-900 dark:text-amber-200">
                    <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden="true" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {status === "proposed" ? (
              <>
                <Button size="sm" onClick={() => onDecide("approved")}>
                  <ThumbsUp aria-hidden="true" /> Approve for submittal
                </Button>
                <Button size="sm" variant="outline" onClick={() => onDecide("rejected")}>
                  <ThumbsDown aria-hidden="true" /> Reject
                </Button>
              </>
            ) : (
              <Button size="sm" variant="outline" onClick={() => onDecide("proposed")}>
                <Undo2 aria-hidden="true" /> Undo
              </Button>
            )}
            <Button size="sm" variant="ghost" asChild>
              <Link href={`/candidates/${m.person_id}`}>
                <UserRound aria-hidden="true" /> Profile
              </Link>
            </Button>
            <Button size="sm" variant="ghost" onClick={onViewResume}>
              <Eye aria-hidden="true" /> Resume
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="sm:ml-auto"
              aria-expanded={open}
              aria-controls={`verdicts-${m.id}`}
              onClick={() => setOpen((o) => !o)}
            >
              Requirements
              <span className="text-xs text-muted-foreground tabular-nums">
                {counts.met ?? 0}/{m.verdicts.length} met
              </span>
              <ChevronDown className={cn("transition-transform", open && "rotate-180")} aria-hidden="true" />
            </Button>
          </div>
          <Gaps verdicts={m.verdicts} />
        </div>
      </div>
      {open && (
        <ul id={`verdicts-${m.id}`} className="divide-y border-t px-4">
          {m.verdicts.map((v, i) => (
            <VerdictRow key={i} v={v} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function Shortlist({ matches, onViewResume }: { matches: Match[]; onViewResume: (t: ViewerTarget) => void }) {
  // Optimistic decisions: shown immediately, rolled back if the API call fails.
  const [overrides, setOverrides] = useState<Record<number, MatchDecision>>({});
  const statusOf = (m: Match) => overrides[m.id] ?? m.status;

  async function decide(m: Match, status: MatchDecision) {
    const previous = statusOf(m);
    setOverrides((o) => ({ ...o, [m.id]: status }));
    try {
      await apiFetch(`/api/matches/${m.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (status === "approved") toast.success(`${m.full_name} approved for submittal`);
      else if (status === "rejected") toast.success(`${m.full_name} rejected`);
    } catch {
      setOverrides((o) => ({ ...o, [m.id]: previous }));
      toast.error(`Couldn't save the decision for ${m.full_name}. Try again.`);
    }
  }

  const sorted = [...matches].sort((a, b) => b.score - a.score);
  const tally = sorted.reduce<Record<string, number>>((acc, m) => ({ ...acc, [m.recommendation]: (acc[m.recommendation] ?? 0) + 1 }), {});
  const approved = sorted.filter((m) => statusOf(m) === "approved").length;

  return (
    <div className="space-y-3">
      <p className="flex gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <Info className="mt-px size-3.5 shrink-0" aria-hidden="true" />
        Scores are computed from the job order&apos;s requirements by code, not from AI opinion. Flags are things to confirm.
      </p>
      <p className="text-sm text-muted-foreground">
        Suggested: <span className="font-medium text-foreground">{tally.submit ?? 0}</span> submit · {tally.consider ?? 0} consider · {tally.pass ?? 0} pass
        {approved > 0 && <> · <span className="font-medium text-foreground">{approved}</span> approved</>}
      </p>
      <ol className="space-y-3">
        {sorted.map((m, i) => (
          <MatchCard
            key={m.id}
            m={m}
            rank={i + 1}
            status={statusOf(m)}
            onDecide={(s) => decide(m, s)}
            onViewResume={() =>
              onViewResume({
                title: m.full_name,
                subtitle: m.headline ?? undefined,
                viewUrl: `/api/candidates/files/${m.resume_file_id}/view`,
                downloadUrl: `/api/candidates/files/${m.resume_file_id}`,
              })
            }
          />
        ))}
      </ol>
    </div>
  );
}
