"use client";

import Image from "next/image";
import { Maximize2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

export type Diagram = {
  src: string;
  title: string;
  alt: string;
  width: number;
  height: number;
  points: string[];
  step: number;
};

/** One D2 diagram with a plain-English walkthrough; click the picture to open it full size. */
export function DiagramCard({ d }: { d: Diagram }) {
  const wide = d.width / d.height > 2;
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardDescription className="text-xs font-medium tracking-wide uppercase">Step {d.step}</CardDescription>
        <CardTitle className="text-lg">{d.title}</CardTitle>
      </CardHeader>
      <CardContent className={wide ? "space-y-5" : "grid gap-6 md:grid-cols-2 md:items-start"}>
        <Dialog>
          <DialogTrigger asChild>
            <button
              type="button"
              className="group relative block w-full overflow-hidden rounded-lg border bg-white p-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              aria-label={`Enlarge diagram: ${d.title}`}
            >
              <Image
                src={d.src}
                alt={d.alt}
                width={d.width}
                height={d.height}
                unoptimized
                className={wide ? "h-auto w-full" : "mx-auto h-auto max-h-[420px] w-auto"}
              />
              <span className="absolute right-2 bottom-2 flex items-center gap-1 rounded-md bg-neutral-900/80 px-2 py-1 text-xs font-medium text-white opacity-90 transition-opacity group-hover:opacity-100">
                <Maximize2 className="size-3" aria-hidden="true" /> Zoom
              </span>
            </button>
          </DialogTrigger>
          <DialogContent className="max-h-[92vh] w-[96vw] max-w-[96vw] overflow-auto p-3 sm:max-w-[96vw] sm:p-4">
            <DialogTitle className="pr-8">{d.title}</DialogTitle>
            <DialogDescription className="sr-only">{d.alt}</DialogDescription>
            <div className="overflow-auto rounded-lg bg-white p-2">
              <Image
                src={d.src}
                alt={d.alt}
                width={d.width}
                height={d.height}
                unoptimized
                className="h-auto w-full min-w-[720px]"
              />
            </div>
          </DialogContent>
        </Dialog>
        <ul className="space-y-2.5 text-sm">
          {d.points.map((p) => (
            <li key={p} className="flex gap-2.5">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />
              <span className="text-muted-foreground [&_strong]:font-medium [&_strong]:text-foreground">{p}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
