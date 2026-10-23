"use client";

import { useState } from "react";
import { CircleCheck, FileWarning } from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { EmptyState } from "@/components/empty-state";
import { ResumeViewer, type ViewerTarget } from "@/components/resume-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi, type NeedsAttention } from "@/lib/api";
import { issueLabel, relativeTime } from "@/lib/format";

/** Files the pipeline couldn't turn into a profile (scanned, corrupt…), with the reason. */
export function NeedsAttentionList() {
  const { data, error, reload } = useApi<NeedsAttention[]>("/api/candidates/needs-attention");
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);

  if (error) return <ApiErrorState error={error} onRetry={reload} />;
  return (
    <Card className="gap-0 py-0">
      <div className="border-b px-4 py-3 text-sm text-muted-foreground">
        These files couldn&apos;t be turned into a profile automatically. Each needs a person to look at it.
      </div>
      {!data && (
        <ul className="divide-y">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="px-4 py-4">
              <Skeleton className="h-10 w-full" />
            </li>
          ))}
        </ul>
      )}
      {data?.length === 0 && (
        <EmptyState icon={CircleCheck} title="Nothing needs attention" description="Every uploaded file was processed." />
      )}
      {data && data.length > 0 && (
        <ul className="divide-y">
          {data.map((f) => (
            <li key={f.resume_file_id} className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 gap-3">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-amber-500/10 text-amber-700 dark:text-amber-300">
                  <FileWarning className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0 space-y-1">
                  <p className="truncate text-sm font-medium">{f.filename}</p>
                  <p className="text-sm text-muted-foreground">{f.reason}</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {f.quality_issues.map((i) => (
                      <Badge key={i} variant="outline" className="font-normal">
                        {issueLabel(i)}
                      </Badge>
                    ))}
                    <span className="text-xs text-muted-foreground">· {relativeTime(f.created_at)}</span>
                  </div>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="self-start sm:self-center"
                onClick={() =>
                  setViewer({
                    title: f.filename,
                    subtitle: f.reason,
                    viewUrl: `/api/candidates/files/${f.resume_file_id}/view`,
                    downloadUrl: `/api/candidates/files/${f.resume_file_id}`,
                  })
                }
              >
                Open file
              </Button>
            </li>
          ))}
        </ul>
      )}
      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
    </Card>
  );
}
