"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, CircleAlert, Loader2, Plus } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api";
import type { JobOrder } from "@/lib/job-types";
import { cn } from "@/lib/utils";

const MIN = 20;
const MAX = 6000;
const STAGES = [
  { label: "Reading your notes", at: 0 },
  { label: "Pulling out requirements", at: 2000 },
  { label: "Drafting questions for the hiring manager", at: 5000 },
];
const EXAMPLE = `- sr structural engineer, healthcare
- client: structural firm, Dallas office
- REQ: TX PE
- REQ: 8+ yrs, hospital / medical office projects
- pref: Revit + RAM Structural System
- hybrid, salary 130-155k`;

function Stages() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => setElapsed(Date.now() - start), 250);
    return () => clearInterval(t);
  }, []);
  const current = STAGES.reduce((idx, s, i) => (elapsed >= s.at ? i : idx), 0);
  return (
    <div className="space-y-2 rounded-lg border bg-muted/30 p-3" role="status" aria-live="polite">
      {STAGES.map((s, i) => (
        <p key={s.label} className={cn("flex items-center gap-2 text-sm", i > current && "text-muted-foreground/60")}>
          {i < current ? (
            <Check className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          ) : i === current ? (
            <Loader2 className="size-4 animate-spin text-brand" aria-hidden="true" />
          ) : (
            <span className="flex size-4 items-center justify-center">
              <span className="size-1.5 rounded-full bg-muted-foreground/40" />
            </span>
          )}
          {s.label}
          {i === current && "…"}
        </p>
      ))}
    </div>
  );
}

export function NewJobOrderDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const len = notes.trim().length;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (len < MIN || len > MAX || pending) return;
    setPending(true);
    setError(null);
    try {
      const jo = await apiFetch<JobOrder>("/api/job-orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: notes.trim() }),
      });
      router.push(`/job-orders/${jo.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? "Today's AI spend cap has been reached. Try again tomorrow, or ask an admin to raise the cap."
          : err instanceof ApiError
            ? err.message
            : "Can't reach the server. Try again.",
      );
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (pending) return; // keep the dialog open while the job order is being created
        setOpen(o);
        if (!o) setError(null);
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus aria-hidden="true" /> New job order
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>New job order</DialogTitle>
            <DialogDescription>
              Paste your notes from the hiring-manager call. Placewise turns them into requirements and questions to ask.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="jo-notes">Call notes</Label>
            <textarea
              id="jo-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={pending}
              rows={9}
              maxLength={MAX}
              placeholder={EXAMPLE}
              className="w-full resize-y rounded-lg border border-input bg-transparent px-3 py-2 font-mono text-[13px] outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60 dark:bg-input/30"
            />
            <p className="flex justify-between text-xs text-muted-foreground">
              <span>{len > 0 && len < MIN ? `At least ${MIN} characters` : "Bullet points are fine. Mark must-haves with REQ."}</span>
              <span className="tabular-nums">
                {len}/{MAX}
              </span>
            </p>
          </div>
          {pending && <Stages />}
          {error && (
            <p role="alert" className="flex items-center gap-2 text-sm text-destructive">
              <CircleAlert className="size-4 shrink-0" aria-hidden="true" /> {error}
            </p>
          )}
          <DialogFooter>
            <Button type="submit" disabled={pending || len < MIN}>
              {pending && <Loader2 className="animate-spin" aria-hidden="true" />}
              {pending ? "Creating…" : "Create job order"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
