"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { Maximize2, Minus, Plus, ScanSearch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export type Diagram = {
  src: string;
  title: string;
  caption: string;
  alt: string;
  width: number;
  height: number;
};

const ZOOMS = [1, 1.5, 2, 3];

/** Full-screen viewer: the SVG on a white panel (the diagrams are light-themed), zoomable and drag-to-pan. */
function DiagramViewer({ d }: { d: Diagram }) {
  const [zoom, setZoom] = useState(0);
  const pane = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const scale = ZOOMS[zoom];

  // Keep the middle of the diagram in view when the zoom level changes.
  useEffect(() => {
    const el = pane.current;
    if (!el) return;
    el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2;
    el.scrollTop = (el.scrollHeight - el.clientHeight) / 2;
  }, [zoom]);

  return (
    <DialogContent className="flex h-[94dvh] w-[98vw] max-w-[98vw] flex-col gap-3 p-3 sm:max-w-[98vw] sm:p-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pr-10">
        <div className="min-w-0 flex-1">
          <DialogTitle className="text-base">{d.title}</DialogTitle>
          <DialogDescription className="text-xs">{d.caption}</DialogDescription>
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="Zoom">
          <Button variant="outline" size="icon-sm" onClick={() => setZoom((z) => Math.max(0, z - 1))} disabled={zoom === 0} aria-label="Zoom out">
            <Minus />
          </Button>
          <span className="w-12 text-center text-xs font-medium tabular-nums" aria-live="polite">
            {zoom === 0 ? "Fit" : `${scale * 100}%`}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => setZoom((z) => Math.min(ZOOMS.length - 1, z + 1))}
            disabled={zoom === ZOOMS.length - 1}
            aria-label="Zoom in"
          >
            <Plus />
          </Button>
        </div>
      </div>
      <div
        ref={pane}
        tabIndex={0}
        aria-label={`${d.title}: scroll or drag to pan`}
        className={cn(
          "min-h-0 flex-1 overflow-auto rounded-lg border bg-white outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          zoom > 0 && "cursor-grab active:cursor-grabbing",
        )}
        onPointerDown={(e) => {
          if (zoom === 0 || !pane.current || e.pointerType !== "mouse") return;
          drag.current = { x: e.clientX, y: e.clientY, left: pane.current.scrollLeft, top: pane.current.scrollTop };
          pane.current.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (!drag.current || !pane.current) return;
          pane.current.scrollLeft = drag.current.left - (e.clientX - drag.current.x);
          pane.current.scrollTop = drag.current.top - (e.clientY - drag.current.y);
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerCancel={() => (drag.current = null)}
      >
        <div
          className={cn("p-4", zoom === 0 && "flex h-full items-center justify-center")}
          style={zoom > 0 ? { width: `${scale * 100}%`, minWidth: 720 } : undefined}
        >
          <Image
            src={d.src}
            alt={d.alt}
            width={d.width}
            height={d.height}
            unoptimized
            draggable={false}
            className={zoom === 0 ? "h-auto max-h-full w-auto max-w-full select-none" : "h-auto w-full select-none"}
          />
        </div>
      </div>
    </DialogContent>
  );
}

/**
 * A clickable diagram preview that opens the full-screen viewer. `variant="wide"` shows the whole
 * diagram at full card width (for the wide Ask flow diagrams); the default is a fixed-height gallery tile.
 */
export function DiagramCard({ d, variant = "tile", className }: { d: Diagram; variant?: "tile" | "wide"; className?: string }) {
  const preview = (
    <DialogTrigger asChild>
      <button
        type="button"
        className={cn(
          "group/diagram relative block w-full overflow-hidden rounded-lg border bg-white outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          variant === "tile" ? "min-h-52 flex-1" : "p-3 sm:p-4",
        )}
        aria-label={`Open diagram full screen: ${d.title}`}
      >
        <Image
          src={d.src}
          alt={d.alt}
          width={d.width}
          height={d.height}
          unoptimized
          className={cn(
            "transition-transform duration-300 group-hover/diagram:scale-[1.02]",
            variant === "tile" ? "absolute inset-3 h-[calc(100%-1.5rem)] w-[calc(100%-1.5rem)] object-contain" : "h-auto w-full",
          )}
        />
        <span className="absolute right-2 bottom-2 flex items-center gap-1 rounded-md bg-neutral-900/80 px-2 py-1 text-xs font-medium text-white shadow-sm transition-opacity group-hover/diagram:opacity-100 sm:opacity-80">
          <Maximize2 className="size-3" aria-hidden="true" /> Zoom
        </span>
      </button>
    </DialogTrigger>
  );

  if (variant === "wide") {
    return (
      <Dialog>
        <figure className="space-y-2">
          {preview}
          <figcaption className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <ScanSearch className="mt-px size-3.5 shrink-0" aria-hidden="true" />
            <span>
              <span className="font-medium text-foreground">{d.title}.</span> {d.caption}
            </span>
          </figcaption>
        </figure>
        <DiagramViewer d={d} />
      </Dialog>
    );
  }

  return (
    <Dialog>
      <div
        className={cn(
          "group/card flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-xs transition-[box-shadow,border-color] duration-150 hover:border-foreground/15 hover:shadow-md",
          className,
        )}
      >
        {preview}
        <div className="space-y-0.5 px-1 pb-1">
          <h3 className="text-sm font-semibold">{d.title}</h3>
          <p className="text-xs leading-relaxed text-muted-foreground">{d.caption}</p>
        </div>
      </div>
      <DiagramViewer d={d} />
    </Dialog>
  );
}
