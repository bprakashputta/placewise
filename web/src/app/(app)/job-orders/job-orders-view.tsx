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
import { disciplineLabel, relativeTime } from "@/lib/format";
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
  if (!row.last_run_status) return <span className="text-sm text-muted-foreground">Not run yet</span>;
  if (row.last_run_status === "running")
    return (
      <span className="flex items-center gap-1.5 text-sm">
        <Loader2 className="size-3.5 animate-spin text-brand" aria-hidden="true" /> Matching…
      </span>
    );
  if (row.last_run_status === "failed")
    return (
      <span className="flex items-center gap-1.5 text-sm text-destructive">
        <CircleX className="size-3.5" aria-hidden="true" /> Failed
      </span>
    );
  return (
    <span className="flex items-center gap-1.5 text-sm">
      <CircleCheck className="size-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
      Done <span className="text-muted-foreground">· {relativeTime(row.last_run_at)}</span>
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
        description="Searches your team is working, each with a ranked, evidence-backed shortlist."
        actions={<NewJobOrderDialog />}
      />
      {error ? (
        <ApiErrorState error={error} onRetry={reload} />
      ) : (
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
                    <TableCell className="max-w-96 px-4 py-2.5 whitespace-normal">
                      <Link href={href} onClick={(e) => e.stopPropagation()} className="font-medium hover:underline focus-visible:underline focus-visible:outline-none">
                        {j.title}
                      </Link>
                      <p className="line-clamp-1 text-xs text-muted-foreground">
                        {j.client ?? "–"} · created {relativeTime(j.created_at)}
                      </p>
                    </TableCell>
                    <TableCell className="hidden px-4 md:table-cell">{j.metro ?? "–"}</TableCell>
                    <TableCell className="hidden px-4 lg:table-cell">{disciplineLabel(j.discipline)}</TableCell>
                    <TableCell className="hidden px-4 sm:table-cell">
                      <RunStatus row={j} />
                    </TableCell>
                    <TableCell className="px-4 text-right">
                      {j.last_run_status === "done" ? (
                        <Badge className="bg-emerald-500/10 text-emerald-700 tabular-nums ring-1 ring-emerald-600/20 ring-inset dark:text-emerald-300">
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
