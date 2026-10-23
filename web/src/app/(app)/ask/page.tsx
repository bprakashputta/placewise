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
        <div className="space-y-6" aria-busy="true">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-[32rem] rounded-xl" />
        </div>
      }
    >
      <AskView />
    </Suspense>
  );
}
