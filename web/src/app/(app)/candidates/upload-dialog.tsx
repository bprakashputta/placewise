"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { CircleAlert, CircleCheck, Copy, FileText, FileUp, Loader2, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ApiError, apiFetch, type IngestJob, type UploadResult } from "@/lib/api";
import { cn } from "@/lib/utils";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";
const POLL_MS = 2000;
const POLL_LIMIT = 150; // ~5 minutes, then stop polling and say so

type Phase =
  | { kind: "idle" }
  | { kind: "uploading" }
  | { kind: "polling"; jobId: number; job?: IngestJob }
  | { kind: "duplicate"; message: string }
  | { kind: "error"; message: string };

const TERMINAL = new Set(["done", "duplicate", "needs_attention", "failed"]);

function checkFile(file: File): string | null {
  if (file.size === 0) return "That file is empty.";
  if (file.size > MAX_BYTES) return "That file is larger than 10 MB.";
  if (!/\.(pdf|docx|txt)$/i.test(file.name)) return "Only PDF, DOCX or TXT resumes are supported.";
  return null;
}

function uploadErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 413) return "That file is larger than 10 MB.";
    if (e.status === 415) return e.message || "Only PDF, DOCX or TXT resumes are supported.";
    return e.message;
  }
  return "Upload failed. Check your connection and try again.";
}

const STEPS = [
  { key: "queued", label: "Queued" },
  { key: "running", label: "Processing" },
  { key: "done", label: "Done" },
];

function Progress({ job, stalled }: { job?: IngestJob; stalled: boolean }) {
  const status = job?.status ?? "queued";
  const activeIndex = status === "queued" ? 0 : status === "running" ? 1 : 2;
  return (
    <div className="space-y-4" aria-live="polite">
      <ol className="flex items-center gap-2">
        {STEPS.map((s, i) => {
          const reached = i <= activeIndex;
          const current = i === activeIndex && !TERMINAL.has(status);
          return (
            <li key={s.key} className="flex flex-1 items-center gap-2">
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                  reached ? "border-brand bg-brand text-white" : "text-muted-foreground",
                )}
              >
                {current ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : i + 1}
              </span>
              <span className={cn("text-xs", reached ? "font-medium" : "text-muted-foreground")}>{s.label}</span>
              {i < STEPS.length - 1 && <span className={cn("h-px flex-1", i < activeIndex ? "bg-brand" : "bg-border")} />}
            </li>
          );
        })}
      </ol>
      {status === "done" && (
        <div className="flex gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-800 dark:text-emerald-200">
          <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>Profile ready. Credentials were checked against quotes from the resume.</p>
        </div>
      )}
      {status === "duplicate" && (
        <div className="flex gap-2 rounded-lg border bg-muted/50 p-3 text-sm">
          <Copy className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <p>This resume is a duplicate of one already on file, so no new profile was created.</p>
        </div>
      )}
      {status === "needs_attention" && (
        <div className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            Needs attention: {job?.error ?? "the file couldn't be read automatically"}. It&apos;s listed under the
            Needs attention tab.
          </p>
        </div>
      )}
      {status === "failed" && (
        <div className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>Processing failed{job?.error ? `: ${job.error}` : ""}. An admin can retry failed jobs.</p>
        </div>
      )}
      {stalled && !TERMINAL.has(status) && (
        <p className="text-sm text-muted-foreground">
          Still processing. You can close this dialog; the candidate will appear in the list when it&apos;s done.
        </p>
      )}
    </div>
  );
}

export function UploadDialog() {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const [polls, setPolls] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const jobId = phase.kind === "polling" ? phase.jobId : null;
  const job = phase.kind === "polling" ? phase.job : undefined;
  const finished = job ? TERMINAL.has(job.status) : false;
  const stalled = polls >= POLL_LIMIT;

  // Poll the ingest job every 2s until it reaches a terminal status (or the poll limit).
  useEffect(() => {
    if (jobId === null || finished || stalled || !open) return;
    const t = setTimeout(async () => {
      try {
        const j = await apiFetch<IngestJob>(`/api/ingest/jobs/${jobId}`);
        setPhase((p) => (p.kind === "polling" && p.jobId === jobId ? { ...p, job: j } : p));
      } catch {
        // transient error: keep polling
      }
      setPolls((n) => n + 1);
    }, POLL_MS);
    return () => clearTimeout(t);
  }, [jobId, finished, stalled, open, polls]);

  function reset() {
    setFile(null);
    setPhase({ kind: "idle" });
    setPolls(0);
  }

  function pick(f: File | undefined) {
    if (!f) return;
    const problem = checkFile(f);
    setFile(f);
    setPhase(problem ? { kind: "error", message: problem } : { kind: "idle" });
  }

  async function upload() {
    if (!file) return;
    setPhase({ kind: "uploading" });
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await apiFetch<UploadResult>("/api/candidates/upload", { method: "POST", body });
      if (!res.queued || res.job_id === null) setPhase({ kind: "duplicate", message: res.message });
      else {
        setPolls(0);
        setPhase({ kind: "polling", jobId: res.job_id });
      }
    } catch (e) {
      setPhase({ kind: "error", message: uploadErrorMessage(e) });
    }
  }

  const busy = phase.kind === "uploading" || (phase.kind === "polling" && !finished && !stalled);
  const personId = job?.status === "done" ? job.result?.person_id : undefined;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <FileUp aria-hidden="true" /> Upload resume
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload a resume</DialogTitle>
          <DialogDescription>PDF, DOCX or TXT, up to 10 MB. Placewise builds a profile in about a minute.</DialogDescription>
        </DialogHeader>

        {(phase.kind === "idle" || phase.kind === "error" || phase.kind === "uploading") && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              pick(e.dataTransfer.files[0]);
            }}
            className={cn(
              "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors",
              dragging ? "border-brand bg-brand-soft" : "bg-muted/30",
            )}
          >
            <UploadCloud className="size-7 text-muted-foreground" aria-hidden="true" />
            {file ? (
              <p className="flex max-w-full items-center gap-1.5 text-sm font-medium">
                <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="truncate">{file.name}</span>
                <span className="shrink-0 text-xs font-normal text-muted-foreground">
                  {(file.size / 1024 / 1024).toFixed(1)} MB
                </span>
              </p>
            ) : (
              <p className="text-sm">Drag a resume here</p>
            )}
            <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()} disabled={phase.kind === "uploading"}>
              {file ? "Choose another file" : "Browse files"}
            </Button>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              className="sr-only"
              aria-label="Resume file"
              tabIndex={-1}
              onChange={(e) => {
                pick(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </div>
        )}

        {phase.kind === "error" && (
          <p role="alert" className="flex items-center gap-2 text-sm text-destructive">
            <CircleAlert className="size-4 shrink-0" aria-hidden="true" /> {phase.message}
          </p>
        )}
        {phase.kind === "duplicate" && (
          <div className="flex gap-2 rounded-lg border bg-muted/50 p-3 text-sm">
            <Copy className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <p>{phase.message}. Nothing new was queued.</p>
          </div>
        )}
        {phase.kind === "polling" && <Progress job={job} stalled={stalled} />}

        <DialogFooter>
          {phase.kind === "polling" || phase.kind === "duplicate" ? (
            <>
              <Button variant="outline" onClick={reset} disabled={busy}>
                Upload another
              </Button>
              {personId ? (
                <Button asChild>
                  <Link href={`/candidates/${personId}`} onClick={() => setOpen(false)}>
                    View candidate
                  </Link>
                </Button>
              ) : (
                <Button onClick={() => setOpen(false)}>
                  {busy ? "Close (keeps processing)" : "Close"}
                </Button>
              )}
            </>
          ) : (
            <Button onClick={upload} disabled={!file || phase.kind === "uploading" || checkFile(file) !== null}>
              {phase.kind === "uploading" && <Loader2 className="animate-spin" aria-hidden="true" />}
              {phase.kind === "uploading" ? "Uploading…" : "Upload"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
