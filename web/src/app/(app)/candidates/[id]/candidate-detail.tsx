"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  BadgeCheck,
  Briefcase,
  Download,
  Eye,
  FileText,
  GraduationCap,
  Info,
  MapPin,
  Plane,
  ShieldAlert,
  ShieldCheck,
  UserX,
} from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { EmptyState } from "@/components/empty-state";
import { QualityBadge } from "@/components/quality-badge";
import { ResumeViewer, type ViewerTarget } from "@/components/resume-viewer";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi, type CandidateDetail as Detail, type Credential } from "@/lib/api";
import {
  credentialLabel,
  disciplineLabel,
  formatDate,
  formatYears,
  humanize,
  initials,
  issueLabel,
  relativeTime,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-emerald-500/10 text-emerald-700 ring-emerald-600/20 dark:text-emerald-300 dark:ring-emerald-400/25",
  pursuing: "bg-sky-500/10 text-sky-700 ring-sky-600/20 dark:text-sky-300 dark:ring-sky-400/25",
  exam_scheduled: "bg-sky-500/10 text-sky-700 ring-sky-600/20 dark:text-sky-300 dark:ring-sky-400/25",
  expired: "bg-muted text-muted-foreground ring-border line-through decoration-1",
};

const RATING_STYLES: Record<string, string> = {
  excellent: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  good: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  fair: "bg-amber-500/10 text-amber-800 dark:text-amber-300",
  poor: "bg-red-500/10 text-red-700 dark:text-red-300",
};

/** A finding about hidden text or AI-directed instructions is a security warning, not just info. */
function isSecurityFinding(f: string) {
  return /hidden|instruction|inject|AI system/i.test(f);
}

function Quote({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <blockquote className={cn("border-l-2 border-border pl-3 text-sm text-muted-foreground italic", className)}>
      {children}
    </blockquote>
  );
}

function CredentialItem({ c }: { c: Credential }) {
  return (
    <li className="space-y-2 py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-sm font-medium">
          {c.status === "active" && <BadgeCheck className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />}
          {credentialLabel(c.key, c.state)}
        </span>
        <Badge className={cn("ring-1 ring-inset", STATUS_STYLES[c.status] ?? STATUS_STYLES.expired)}>{humanize(c.status)}</Badge>
      </div>
      <Quote>
        <span className="not-italic text-xs font-medium tracking-wide text-muted-foreground/80 uppercase">From the resume: </span>
        &ldquo;{c.quote}&rdquo;
      </Quote>
    </li>
  );
}

function Header({ d, onView }: { d: Detail; onView: () => void }) {
  const p = d.profile;
  const meta = [
    p.city && { icon: MapPin, text: `${p.city}${p.state ? `, ${p.state}` : ""}${d.metro ? ` · ${d.metro} metro` : ""}` },
    d.years_experience !== null && { icon: Briefcase, text: `${formatYears(d.years_experience)} experience` },
    p.open_to_relocation && { icon: Plane, text: "Open to relocation" },
  ].filter(Boolean) as { icon: typeof MapPin; text: string }[];
  return (
    <Card>
      <CardContent className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 gap-4">
          <Avatar className="size-14 shrink-0">
            <AvatarFallback className="bg-brand-soft text-lg font-semibold text-brand">{initials(p.full_name)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">{p.full_name}</h1>
              <QualityBadge quality={d.quality} issues={d.quality_issues} />
            </div>
            {p.headline && <p className="text-sm text-muted-foreground">{p.headline}</p>}
            <div className="flex flex-wrap gap-1.5">
              {p.discipline && <Badge variant="secondary">{disciplineLabel(p.discipline)}</Badge>}
              {p.subdiscipline && (
                <Badge variant="outline" className="font-normal">
                  {humanize(p.subdiscipline)}
                </Badge>
              )}
            </div>
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              {meta.map((m) => (
                <li key={m.text} className="flex items-center gap-1.5">
                  <m.icon className="size-3.5" aria-hidden="true" />
                  {m.text}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button onClick={onView}>
            <Eye aria-hidden="true" /> View resume
          </Button>
          <Button variant="outline" asChild>
            <a href={`/api/candidates/files/${d.resume_file_id}`} download>
              <Download aria-hidden="true" /> Download
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Experience({ jobs }: { jobs: Detail["profile"]["jobs"] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Experience</CardTitle>
      </CardHeader>
      <CardContent>
        {jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No jobs listed.</p>
        ) : (
          <ol className="relative space-y-6 border-l border-border pl-6">
            {jobs.map((j, i) => (
              <li key={i} className="relative">
                <span
                  className={cn(
                    "absolute top-1.5 -left-[29px] size-2.5 rounded-full ring-4 ring-card",
                    i === 0 ? "bg-brand" : "bg-muted-foreground/40",
                  )}
                  aria-hidden="true"
                />
                <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                  <p className="text-sm font-medium">{j.title ?? "Untitled role"}</p>
                  <p className="shrink-0 text-xs text-muted-foreground tabular-nums">
                    {[j.start, j.end].filter(Boolean).join(" – ") || "–"}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">{[j.employer, j.location].filter(Boolean).join(" · ")}</p>
                {j.highlights.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-sm marker:text-muted-foreground/60">
                    {j.highlights.map((h, k) => (
                      <li key={k}>{h}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

function QualityCard({ d }: { d: Detail }) {
  const wq = d.profile.writing_quality;
  const security = d.findings.filter(isSecurityFinding);
  const other = d.findings.filter((f) => !isSecurityFinding(f));
  return (
    <Card id="quality" className="scroll-mt-20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {security.length ? (
            <ShieldAlert className="size-4 text-fuchsia-600 dark:text-fuchsia-400" aria-hidden="true" />
          ) : (
            <ShieldCheck className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          )}
          Quality &amp; security
        </CardTitle>
        <CardDescription>What the screening found before any AI read this resume.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {security.length > 0 && (
          <div role="alert" className="space-y-1.5 rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/10 p-3 text-sm text-fuchsia-900 dark:text-fuchsia-200">
            <p className="flex items-center gap-1.5 font-medium">
              <ShieldAlert className="size-4 shrink-0" aria-hidden="true" /> Security warning
            </p>
            <ul className="list-disc space-y-1 pl-5">
              {security.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>
        )}
        {other.length > 0 && (
          <ul className="space-y-1.5 text-sm">
            {other.map((f) => (
              <li key={f} className="flex gap-2">
                <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                {f}
              </li>
            ))}
          </ul>
        )}
        {d.findings.length === 0 && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="size-4 shrink-0" aria-hidden="true" /> No hidden text or AI-directed instructions found.
          </p>
        )}

        {wq && (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-sm font-medium">Writing quality</p>
                <p className="text-xs text-muted-foreground">How well the resume is written (judged by AI)</p>
              </div>
              <Badge className={cn("capitalize", RATING_STYLES[wq.rating] ?? "bg-muted text-muted-foreground")}>{wq.rating}</Badge>
            </div>
            {wq.issues.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {wq.issues.map((i) => (
                  <Badge key={i} variant="outline" className="font-normal">
                    {issueLabel(i)}
                  </Badge>
                ))}
              </div>
            )}
            {wq.evidence.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-muted-foreground">Evidence</p>
                {wq.evidence.map((e, i) => (
                  <Quote key={i}>&ldquo;{e}&rdquo;</Quote>
                ))}
              </div>
            )}
          </div>
        )}

        {d.validation_notes.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Validation notes</p>
            <ul className="space-y-1.5">
              {d.validation_notes.map((n) => (
                <li key={n} className="flex gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-2 text-sm text-amber-900 dark:text-amber-200">
                  <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  {n}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Chips({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((s) => (
        <Badge key={s} variant="secondary" className="font-normal">
          {s}
        </Badge>
      ))}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading candidate">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-36 rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-96 rounded-xl lg:col-span-2" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    </div>
  );
}

export function CandidateDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const valid = /^\d+$/.test(id);
  const { data: d, error, reload } = useApi<Detail>(valid ? `/api/candidates/${id}` : null);
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);

  const back = (
    <Link href="/candidates" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="size-4" aria-hidden="true" /> Candidates
    </Link>
  );

  if (!valid || error?.status === 404) {
    return (
      <div className="space-y-6">
        {back}
        <Card className="py-0">
          <EmptyState
            icon={UserX}
            title="Candidate not found"
            description="This profile doesn't exist or was replaced by a newer version."
            action={
              <Button variant="outline" asChild>
                <Link href="/candidates">Back to candidates</Link>
              </Button>
            }
          />
        </Card>
      </div>
    );
  }
  if (error) return <div className="space-y-6">{back}<ApiErrorState error={error} onRetry={reload} /></div>;
  if (!d) return <DetailSkeleton />;

  const p = d.profile;
  const openViewer = () =>
    setViewer({
      title: p.full_name,
      subtitle: d.filename,
      viewUrl: `/api/candidates/files/${d.resume_file_id}/view`,
      downloadUrl: `/api/candidates/files/${d.resume_file_id}`,
    });

  return (
    <div className="space-y-6">
      {back}
      <Header d={d} onView={openViewer} />
      {d.findings.some(isSecurityFinding) && (
        <a
          href="#quality"
          className="flex items-center gap-2 rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/10 px-3 py-2 text-sm text-fuchsia-900 hover:bg-fuchsia-500/15 dark:text-fuchsia-200"
        >
          <ShieldAlert className="size-4 shrink-0" aria-hidden="true" />
          <span>
            <span className="font-medium">This resume contained hidden instructions aimed at AI systems.</span> They were removed before
            extraction. See Quality &amp; security.
          </span>
        </a>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          {p.summary && (
            <Card>
              <CardHeader>
                <CardTitle>Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{p.summary}</p>
              </CardContent>
            </Card>
          )}
          <Experience jobs={p.jobs} />
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GraduationCap className="size-4 text-muted-foreground" aria-hidden="true" /> Education
              </CardTitle>
            </CardHeader>
            <CardContent>
              {p.education.length === 0 ? (
                <p className="text-sm text-muted-foreground">No education listed.</p>
              ) : (
                <ul className="space-y-3">
                  {p.education.map((e, i) => (
                    <li key={i} className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                      <div>
                        <p className="text-sm font-medium">{e.degree ?? "–"}</p>
                        <p className="text-sm text-muted-foreground">{e.school ?? "–"}</p>
                      </div>
                      {e.year && <p className="text-xs text-muted-foreground tabular-nums">{e.year}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Side column first on phones: credentials and security findings matter most to a recruiter. */}
        <div className="order-first min-w-0 space-y-6 lg:order-none">
          <Card>
            <CardHeader>
              <CardTitle>Credentials</CardTitle>
              <CardDescription>Each one is backed by the exact text from the resume. Only active licenses count in search.</CardDescription>
            </CardHeader>
            <CardContent>
              {p.credentials.length === 0 ? (
                <p className="text-sm text-muted-foreground">No licenses or certifications found.</p>
              ) : (
                <ul className="divide-y">
                  {p.credentials.map((c, i) => (
                    <CredentialItem key={`${c.key}-${c.state}-${i}`} c={c} />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <QualityCard d={d} />

          <Card>
            <CardHeader>
              <CardTitle>Skills &amp; sectors</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Software</p>
                <Chips items={d.software.length ? d.software : p.software} empty="None listed" />
              </div>
              <div className="space-y-2">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Sectors</p>
                <Chips items={(d.sectors.length ? d.sectors : p.sectors).map(humanize)} empty="None listed" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Resume versions</CardTitle>
              <CardDescription>The current version feeds the profile above.</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {d.versions.map((v) => (
                  <li
                    key={v.resume_file_id}
                    className={cn("flex items-start gap-2.5 rounded-lg border p-2.5", v.is_current && "border-brand/40 bg-brand-soft/40")}
                  >
                    <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-medium" title={v.filename}>
                          {v.filename}
                        </p>
                        {v.is_current && <Badge className="shrink-0">Current</Badge>}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {humanize(v.status)} · <span title={formatDate(v.created_at)}>{relativeTime(v.processed_at ?? v.created_at)}</span>
                      </p>
                    </div>
                    {v.quality && <QualityBadge quality={v.quality} short className="shrink-0" />}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>

      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
    </div>
  );
}
