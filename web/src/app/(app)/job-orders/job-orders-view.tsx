"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { BriefcaseBusiness, CircleCheck, CircleX, Loader2 } from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/lib/api";
import { capitalize, disciplineLabel, relativeTime } from "@/lib/format";
import type { JobOrderRow } from "@/lib/job-types";
import { NewJobOrderDialog } from "./new-job-order-dialog";

const COLUMNS = [
  { label: "Job order" },
  { label: "Metro", className: "hidden md:table-cell" },
  { label: "Discipline", className: "hidden lg:table-cell" },
  { label: "Last match", className: "hidden sm:table-cell" },
  { label: "To submit", className: "text-right" },
];

function RunStatus({ row }: { row: JobOrderRow }) {
  if (!row.last_run_status) return <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground ring-1 ring-border ring-inset"><span className="size-1.5 rounded-full bg-muted-foreground/50" aria-hidden="true" />Not run yet</span>;
  if (row.last_run_status === "running")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand-strong ring-1 ring-brand/15 ring-inset">
        <Loader2 className="size-3 animate-spin" aria-hidden="true" /> Matching…
      </span>
    );
  if (row.last_run_status === "failed")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger-strong ring-1 ring-danger/20 ring-inset">
        <CircleX className="size-3.5" aria-hidden="true" /> Failed
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-2 py-0.5 text-xs font-medium text-success-strong ring-1 ring-success/25 ring-inset">
      <CircleCheck className="size-3" aria-hidden="true" />
      Done <span className="font-normal opacity-75">· {relativeTime(row.last_run_at)}</span>
    </span>
  );
}

export function JobOrdersView() {
  const router = useRouter();
  const { data, error, reload } = useApi<JobOrderRow[]>("/api/job-orders");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Job orders"
        icon={BriefcaseBusiness}
        description="Searches your team is working, each with a ranked, evidence-backed shortlist."
        actions={<NewJobOrderDialog />}
      />
      {error ? (
        <ApiErrorState error={error} onRetry={reload} />
      ) : (
        <Card className="gap-0 overflow-hidden py-0">
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow className="hover:bg-transparent">
                {COLUMNS.map((c) => (
                  <TableHead key={c.label} className={`h-10 px-4 text-[11px] font-semibold tracking-[0.06em] text-muted-foreground uppercase ${c.className ?? ""}`}>
                    {c.label}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {!data &&
                Array.from({ length: 6 }, (_, i) => (
                  <TableRow key={i} className="hover:bg-transparent">
                    {COLUMNS.map((c) => (
                      <TableCell key={c.label} className={`px-4 py-3 ${c.className ?? ""}`}>
                        <Skeleton className={c.label === "Job order" ? "h-9 w-56" : "h-4 w-16"} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              {data?.length === 0 && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={COLUMNS.length} className="p-0 whitespace-normal">
                    <EmptyState
                      icon={BriefcaseBusiness}
                      title="No job orders yet"
                      description="Paste notes from a hiring-manager call to create your first one."
                    />
                  </TableCell>
                </TableRow>
              )}
              {data?.map((j) => {
                const href = `/job-orders/${j.id}`;
                return (
                  <TableRow key={j.id} className="cursor-pointer" onClick={() => router.push(href)}>
                    <TableCell className="max-w-96 px-4 py-3 whitespace-normal">
                      <Link href={href} onClick={(e) => e.stopPropagation()} className="font-medium hover:underline focus-visible:underline focus-visible:outline-none">
                        {j.title}
                      </Link>
                      <p className="line-clamp-1 text-xs text-muted-foreground">
                        {j.client && `${capitalize(j.client)} · `}created {relativeTime(j.created_at)}
                      </p>
                    </TableCell>
                    <TableCell className="hidden px-4 md:table-cell">{j.metro ?? "–"}</TableCell>
                    <TableCell className="hidden px-4 lg:table-cell">{disciplineLabel(j.discipline)}</TableCell>
                    <TableCell className="hidden px-4 sm:table-cell">
                      <RunStatus row={j} />
                    </TableCell>
                    <TableCell className="px-4 text-right">
                      {j.last_run_status === "done" ? (
                        <Badge className="min-w-7 bg-success-soft text-success-strong tabular-nums ring-1 ring-success/25 ring-inset">
                          {j.submit_count ?? 0}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">–</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
