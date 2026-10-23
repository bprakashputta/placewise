"use client";

import { useEffect, useState } from "react";
import { Download, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

export type ViewerTarget = { title: string; viewUrl: string; downloadUrl: string; subtitle?: string };
type Load = { state: "loading" } | { state: "ready"; url: string } | { state: "error"; message: string };

// In-page resume viewer on the shadcn (Radix) Dialog: focus is trapped inside, Esc and the overlay
// close it, and focus returns to whatever opened it. The file is fetched once and shown in a frame;
// "Open in new tab" is the fallback when the browser can't show it inline.
export function ResumeViewer({ target, onClose }: { target: ViewerTarget | null; onClose: () => void }) {
  const [load, setLoad] = useState<Load>({ state: "loading" });

  useEffect(() => {
    if (!target) return;
    let objectUrl: string | null = null;
    let alive = true;
    // Reset to the spinner when a different resume is opened; intentional, not a cascade.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoad({ state: "loading" });
    fetch(target.viewUrl, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail ?? `Couldn't load this resume (error ${res.status}).`);
        }
        const blob = await res.blob();
        if (!alive) return; // closed while loading: don't create a URL nobody will revoke
        objectUrl = URL.createObjectURL(blob);
        setLoad({ state: "ready", url: objectUrl });
      })
      .catch((e: Error) => alive && setLoad({ state: "error", message: e.message }));
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [target]);

  return (
    <Dialog open={target !== null} onOpenChange={(open) => !open && onClose()}>
      {target && (
        <DialogContent
          showCloseButton={false}
          className="flex h-[calc(100dvh-1.5rem)] w-full max-w-[calc(100%-1.5rem)] flex-col gap-0 overflow-hidden p-0 shadow-2xl sm:h-[calc(100dvh-3rem)] sm:max-w-5xl"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div className="min-w-0 flex-1">
              <DialogTitle className="truncate text-base leading-normal">{target.title}</DialogTitle>
              <DialogDescription className="truncate text-xs">{target.subtitle ?? "Resume"}</DialogDescription>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button variant="ghost" size="sm" asChild>
                <a href={target.viewUrl} target="_blank" rel="noopener noreferrer">
                  <ExternalLink aria-hidden="true" /> Open in new tab
                </a>
              </Button>
              <Button size="sm" asChild>
                <a href={target.downloadUrl} download>
                  <Download aria-hidden="true" /> Download
                </a>
              </Button>
              <DialogClose asChild>
                <Button variant="outline" size="sm">
                  Close
                </Button>
              </DialogClose>
            </div>
          </div>
          {load.state === "loading" && (
            <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Loading resume…</div>
          )}
          {load.state === "error" && (
            <div className="flex flex-1 items-center justify-center p-8">
              <div className="max-w-md rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
                <p className="mb-1 font-medium">Can&apos;t show this resume here</p>
                <p>{load.message}</p>
              </div>
            </div>
          )}
          {load.state === "ready" && (
            <iframe src={load.url} title={`Resume: ${target.title}`} className="h-full w-full flex-1 bg-neutral-100" />
          )}
        </DialogContent>
      )}
    </Dialog>
  );
}
