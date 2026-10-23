"use client";

import { useEffect, useRef, useState } from "react";

export type ViewerTarget = { title: string; viewUrl: string; downloadUrl: string; subtitle?: string };
type Load = { state: "loading" } | { state: "ready"; url: string } | { state: "error"; message: string };

// In-page resume viewer: shows the PDF in place, with Download and Close (Esc also closes).
// The file is fetched once. A PDF is shown in the frame; an error becomes a readable message.
export function ResumeViewer({ target, onClose }: { target: ViewerTarget | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const [load, setLoad] = useState<Load>({ state: "loading" });

  // Keep the latest onClose in a ref so parent re-renders (the 2s poll) don't re-run the effect,
  // which used to steal focus back to Close every poll.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  const openerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!target) return;
    openerRef.current = document.activeElement;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCloseRef.current();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      (openerRef.current as HTMLElement | null)?.focus?.(); // return focus to what opened the viewer
    };
  }, [target]);

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

  if (!target) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 backdrop-blur-sm sm:p-6"
         onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={`Resume: ${target.title}`}
           className="flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-neutral-900"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-3 border-b border-neutral-200 px-4 py-3 dark:border-neutral-800">
          <div className="min-w-0">
            <p className="truncate font-medium">{target.title}</p>
            {target.subtitle && <p className="truncate text-xs text-neutral-500">{target.subtitle}</p>}
          </div>
          <div className="flex shrink-0 gap-2">
            <a href={target.downloadUrl} download
               className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">
              Download
            </a>
            <button ref={closeRef} onClick={onClose}
                    className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-800">
              Close
            </button>
          </div>
        </div>
        {load.state === "loading" && (
          <div className="flex flex-1 items-center justify-center text-sm text-neutral-500">Loading resume…</div>
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
      </div>
    </div>
  );
}
