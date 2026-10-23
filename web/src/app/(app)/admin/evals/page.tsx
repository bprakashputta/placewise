import type { Metadata } from "next";
import { FlaskConical } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";

export const metadata: Metadata = { title: "Evals" };

export default function EvalsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Evals"
        description="Extraction accuracy, match quality and evidence grounding, measured against the synthetic answer key."
      />
      <Card className="py-0">
        <EmptyState
          icon={FlaskConical}
          title="No eval runs yet"
          description="Eval results appear here after the first run against the held-out test split."
        />
      </Card>
    </div>
  );
}
