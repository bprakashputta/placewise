import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { JobOrderDetail } from "./job-order-detail";

export const metadata: Metadata = { title: "Job order" };

export default function JobOrderPage({ params }: PageProps<"/job-orders/[id]">) {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <JobOrderDetail params={params} />
    </Suspense>
  );
}
