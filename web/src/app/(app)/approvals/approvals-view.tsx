"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ClipboardCheck } from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError, apiFetch } from "@/lib/api";
import { capitalize, formatDate, licenseLabel, relativeTime } from "@/lib/format";
import type { JobOrderRow, Match, MatchesResponse } from "@/lib/job-types";

type Approved = { match: Match; job: JobOrderRow; shortlistedAt: string | null };

const COLUMNS = [
  { label: "Candidate" },
  { label: "Job order", className: "hidden sm:table-cell" },
  { label: "Score", className: "text-right" },
  { label: "Approved", className: "hidden md:table-cell" },
];

/**
 * Approved matches across every job order. There is no cross-job endpoint yet, so this reads the
 * job-order list and each job's latest shortlist (fine at demo scale: ~15 job orders).
 */
function useApproved() {
  const [state, setState] = useState<{ items?: Approved[]; error?: ApiError }>({});
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const jobs = await apiFetch<JobOrderRow[]>("/api/job-orders");
        const withRuns = jobs.filter((j) => j.last_run_id);
        const results = await Promise.all(
          withRuns.map((j) =>
            apiFetch<MatchesResponse>(`/api/job-orders/${j.id}/matches`)
              .then((r) => ({ job: j, r }))
              .catch((e: unknown) => {
                if (e instanceof ApiError && e.status === 404) return null; // no run yet
                throw e;
              }),
          ),
        );
        const items = results
          .flatMap((x) =>
            x ? x.r.matches.filter((m) => m.status === "approved").map((m) => ({ match: m, job: x.job, shortlistedAt: (m as { decided_at?: string | null }).decided_at ?? x.r.run?.finished_at ?? null })) : [],
          )
          .sort((a, b) => (b.shortlistedAt ?? "").localeCompare(a.shortlistedAt ?? "") || b.match.score - a.match.score);
        if (alive) setState({ items });
      } catch (e) {
        if (alive) setState({ error: e instanceof ApiError ? e : new ApiError(0, "Can't reach the API") });
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);
  return { ...state, reload: () => setNonce((n) => n + 1) };
}

export function ApprovalsView() {
  const router = useRouter();
  const { items, error, reload } = useApproved();

  return (
    <div className="space-y-6">
      <PageHeader title="Approvals" description="Candidates approved for submittal, across all job orders. Nothing is sent automatically." />
      {error ? (
        <ApiErrorState error={error} onRetry={reload} />
      ) : items && items.length === 0 ? (
        <Card className="py-0">
          <EmptyState
            icon={ClipboardCheck}
            title="No approved candidates yet"
            description="Open a job order and choose “Approve for submittal” on a shortlisted candidate. Approved candidates collect here."
          />
        </Card>
      ) : (
        <>
          {items && (
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground tabular-nums">{items.length}</span> approved for submittal
            </p>
          )}
          <Card className="gap-0 overflow-hidden py-0">
            <Table>
              <TableHeader className="bg-muted/40">
                <TableRow className="hover:bg-transparent">
                  {COLUMNS.map((c) => (
                    <TableHead key={c.label} className={`h-10 px-4 text-xs font-medium tracking-wide text-muted-foreground uppercase ${c.className ?? ""}`}>
                      {c.label}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {!items &&
                  Array.from({ length: 4 }, (_, i) => (
                    <TableRow key={i} className="hover:bg-transparent">
                      {COLUMNS.map((c) => (
                        <TableCell key={c.label} className={`px-4 py-3 ${c.className ?? ""}`}>
                          <Skeleton className={c.label === "Candidate" ? "h-9 w-48" : "h-4 w-16"} />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                {items?.map(({ match: m, job, shortlistedAt }) => {
                  const jobHref = `/job-orders/${job.id}`;
                  return (
                    <TableRow key={m.id} className="cursor-pointer" onClick={() => router.push(jobHref)}>
                      <TableCell className="max-w-80 px-4 py-2.5 whitespace-normal">
                        <Link
                          href={`/candidates/${m.person_id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="font-medium hover:underline focus-visible:underline focus-visible:outline-none"
                        >
                          {m.full_name}
                        </Link>
                        <p className="line-clamp-1 text-xs text-muted-foreground">
                          {[m.headline, ...m.license_codes.map(licenseLabel)].filter(Boolean).join(" · ") || "–"}
                        </p>
                        <p className="line-clamp-1 text-xs text-muted-foreground sm:hidden">For {job.title}</p>
                      </TableCell>
                      <TableCell className="hidden max-w-72 px-4 whitespace-normal sm:table-cell">
                        <Link href={jobHref} onClick={(e) => e.stopPropagation()} className="text-sm hover:underline">
                          {job.title}
                        </Link>
                        {job.client && <p className="line-clamp-1 text-xs text-muted-foreground">{capitalize(job.client)}</p>}
                      </TableCell>
                      <TableCell className="px-4 text-right font-medium tabular-nums">{Math.round(m.score)}</TableCell>
                      <TableCell className="hidden px-4 text-muted-foreground md:table-cell">
                        <span title={formatDate(shortlistedAt)}>{relativeTime(shortlistedAt)}</span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Card>
        </>
      )}
    </div>
  );
}
