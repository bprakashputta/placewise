import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { EvalNumbers } from "../eval-numbers";

export const metadata: Metadata = { title: "Evals" };

export default function EvalsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Evals"
        description="Extraction accuracy and screening, measured against the synthetic answer key."
      />
      <EvalNumbers headingId="eval-numbers-heading" title="Resume ingest" />
      <p className="text-xs text-muted-foreground">
        These are fixed results from the last eval run, not live numbers. Synthetic resumes are cleaner than real ones, so treat them as an
        optimistic upper bound.
      </p>
    </div>
  );
}
