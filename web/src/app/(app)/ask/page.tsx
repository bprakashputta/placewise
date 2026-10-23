import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { AskView } from "./ask-view";

export const metadata: Metadata = { title: "Ask" };

// The selected chat lives in the URL (?c=<id>, read with useSearchParams), so the view renders inside Suspense.
export default function AskPage() {
  return (
    <Suspense
      fallback={
        <div data-ask-workspace className="flex h-[calc(100svh-3.5rem)] sm:h-[calc(100svh-4rem)] w-full" aria-busy="true">
          <div className="hidden w-[248px] shrink-0 space-y-3 border-r p-3 lg:block">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
          <div className="flex-1" />
        </div>
      }
    >
      <AskView />
    </Suspense>
  );
}
