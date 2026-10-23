import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { CandidatesView } from "./candidates-view";

export const metadata: Metadata = { title: "Candidates" };

// The view reads filters from the URL (useSearchParams), so it renders inside Suspense.
export default function CandidatesPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6" aria-busy="true">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      }
    >
      <CandidatesView />
    </Suspense>
  );
}
