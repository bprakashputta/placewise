"use client";

import { useEffect, useRef } from "react";

export type ViewerTarget = { title: string; viewUrl: string; downloadUrl: string; subtitle?: string };

// In-page resume viewer: shows the PDF in place, with Download and Close (Esc also closes).
export function ResumeViewer({ target, onClose }: { target: ViewerTarget | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!target) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden"; // stop the page behind from scrolling
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [target, onClose]);

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
        <iframe src={target.viewUrl} title={`Resume: ${target.title}`} className="h-full w-full flex-1 bg-neutral-100" />
      </div>
    </div>
  );
}
