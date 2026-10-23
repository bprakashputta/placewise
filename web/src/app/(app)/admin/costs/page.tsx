import type { Metadata } from "next";
import { CircleDollarSign } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";

export const metadata: Metadata = { title: "AI costs" };

export default function CostsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="AI costs"
        description="Model and embedding spend per resume, per shortlist and per day."
      />
      <Card className="py-0">
        <EmptyState
          icon={CircleDollarSign}
          title="No AI usage recorded"
          description="Spend shows up here as soon as Placewise makes its first model call."
        />
      </Card>
    </div>
  );
}
