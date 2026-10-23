import type { Metadata } from "next";
import { ClipboardCheck } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Approvals"
        description="Submittals and outreach drafts waiting for a human decision."
      />
      <Card className="py-0">
        <EmptyState
          icon={ClipboardCheck}
          title="Nothing to approve"
          description="Submittals and outreach drafts land here for review. Nothing is sent until you approve it."
        />
      </Card>
    </div>
  );
}
