import type { Metadata } from "next";
import { BriefcaseBusiness, ClipboardCheck, FileUp, Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardView } from "./dashboard-view";

export const metadata: Metadata = { title: "Dashboard" };

const STEPS = [
  { title: "Ingest resumes", body: "Resumes become structured, searchable profiles with credentials backed by resume quotes.", icon: FileUp },
  { title: "Create a job order", body: "Paste hiring-manager notes; Placewise drafts the requirements.", icon: BriefcaseBusiness },
  { title: "Review shortlist", body: "Ranked candidates, each requirement backed by a quote from the resume.", icon: ClipboardCheck },
  { title: "Approve outreach", body: "Nothing sends until you approve the submittal or message.", icon: Send },
];

export default function DashboardPage() {
  return (
    <DashboardView>
      <Card className="h-full">
        <CardHeader>
          <CardTitle>Getting started</CardTitle>
          <CardDescription>The Placewise pipeline, from resume to approved outreach.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-3 sm:grid-cols-2">
            {STEPS.map((step, i) => (
              <li key={step.title} className="relative flex flex-col gap-3 rounded-lg border bg-muted/30 p-4">
                <div className="flex items-center justify-between">
                  <span className="flex size-8 items-center justify-center rounded-md bg-brand-soft text-brand">
                    <step.icon className="size-4" aria-hidden="true" />
                  </span>
                  <Badge variant="outline" className="text-muted-foreground">
                    Step {i + 1}
                  </Badge>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium">{step.title}</p>
                  <p className="text-sm text-muted-foreground">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </DashboardView>
  );
}
