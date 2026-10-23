import type { Metadata } from "next";
import { BriefcaseBusiness, Plus } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export const metadata: Metadata = { title: "Job Orders" };

export default function JobOrdersPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Job Orders"
        description="Client searches, their structured requirements and shortlists."
        actions={
          <Button disabled>
            <Plus aria-hidden="true" /> New job order
          </Button>
        }
      />
      <Card className="py-0">
        <EmptyState
          icon={BriefcaseBusiness}
          title="No job orders yet"
          description="Create a job order from hiring-manager notes and Placewise will draft the requirements and find matching candidates."
          action={
            <Button disabled>
              <Plus aria-hidden="true" /> New job order
            </Button>
          }
        />
      </Card>
    </div>
  );
}
