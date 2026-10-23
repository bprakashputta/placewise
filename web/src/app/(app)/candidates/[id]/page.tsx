import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { CandidateDetail } from "./candidate-detail";

export const metadata: Metadata = { title: "Candidate" };

// params is a Promise in Next 16; the client view unwraps it with use() inside Suspense.
export default function CandidatePage({ params }: PageProps<"/candidates/[id]">) {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <CandidateDetail params={params} />
    </Suspense>
  );
}
