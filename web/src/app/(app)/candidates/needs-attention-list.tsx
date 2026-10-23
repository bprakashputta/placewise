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
import { humanize, issueLabel, relativeTime } from "@/lib/format";

/** Parser reasons (e.g. "corrupt DOCX (BadZipFile)") → a plain sentence plus what the recruiter should do. */
function explainReason(reason: string | null | undefined): { text: string; todo: string } {
  const r = (reason ?? "").toLowerCase();
  if (r.includes("ocr") || r.includes("no text layer") || r.includes("scanned"))
    return {
      text: "Scanned image: the text can't be read.",
      todo: "Ask the candidate for a Word file or a text-based PDF.",
    };
  if (r.includes("corrupt docx"))
    return {
      text: "The Word file is damaged and won't open.",
      todo: "Ask the candidate to send it again.",
    };
  if (r.includes("corrupt pdf"))
    return {
      text: "The PDF is damaged and won't open.",
      todo: "Ask the candidate to send it again.",
    };
  if (r.includes("almost no text") || r.includes("almost empty") || r.includes("no readable text"))
    return {
      text: "The file has almost no readable text.",
      todo: "Open it to check, then ask the candidate for a complete resume.",
    };
  if (r.includes("unsupported"))
    return {
      text: "This file type isn't supported.",
      todo: "Ask the candidate for a PDF or Word file.",
    };
  const text = reason ? humanize(reason) : "This file couldn't be read.";
  return { text: /[.!?]$/.test(text) ? text : `${text}.`, todo: "Open the file to check it, then ask the candidate for a new copy if needed." };
}

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
          {data.map((f) => {
            const why = explainReason(f.reason);
            return (
            <li key={f.resume_file_id} className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 gap-3">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-amber-500/10 text-amber-700 dark:text-amber-300">
                  <FileWarning className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0 space-y-1">
                  <p className="truncate text-sm font-medium">{f.filename}</p>
                  <p className="text-sm">{why.text}</p>
                  <p className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">What to do:</span> {why.todo}
                  </p>
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
                    subtitle: why.text,
                    viewUrl: `/api/candidates/files/${f.resume_file_id}/view`,
                    downloadUrl: `/api/candidates/files/${f.resume_file_id}`,
                  })
                }
              >
                Open file
              </Button>
            </li>
            );
          })}
        </ul>
      )}
      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
    </Card>
  );
}
