import type { Metadata } from "next";
import { BriefcaseBusiness, ClipboardCheck, FileUp, Send } from "lucide-react";
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
      <Card>
        <CardHeader>
          <CardTitle>How Placewise works</CardTitle>
          <CardDescription>The pipeline, from resume to approved outreach.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <li key={step.title} className="relative flex gap-3 lg:flex-col">
                {/* Connector line between steps on wide screens. */}
                {i < STEPS.length - 1 && (
                  <span className="absolute top-4 left-11 hidden h-px w-[calc(100%-2rem)] bg-border lg:block" aria-hidden="true" />
                )}
                <span className="relative flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand ring-1 ring-brand/15 ring-inset">
                  <step.icon className="size-4" aria-hidden="true" />
                </span>
                <div className="space-y-1">
                  <p className="text-sm font-medium">
                    <span className="mr-1.5 text-xs text-muted-foreground tabular-nums">{i + 1}.</span>
                    {step.title}
                  </p>
                  <p className="text-[13px] leading-relaxed text-muted-foreground">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </DashboardView>
  );
}
