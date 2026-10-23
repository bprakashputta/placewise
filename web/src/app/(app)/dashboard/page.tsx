import type { Metadata } from "next";
import { BriefcaseBusiness, CircleDollarSign, ClipboardCheck, FileUp, ListChecks, Send, Users } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Dashboard" };

// Values show "–" until the ingest and match blocks provide real numbers. No fake data.
const STATS = [
  { label: "Candidates", caption: "Profiles built from ingested resumes", icon: Users },
  { label: "Open job orders", caption: "Searches your team is working", icon: BriefcaseBusiness },
  { label: "Shortlists awaiting review", caption: "Ranked candidates ready for a recruiter", icon: ListChecks },
  { label: "AI spend today", caption: "Model and embedding cost, in USD", icon: CircleDollarSign },
];

const STEPS = [
  { title: "Ingest resumes", body: "Resumes become structured, searchable profiles with verified credentials.", icon: FileUp },
  { title: "Create a job order", body: "Paste hiring-manager notes; Placewise drafts the requirements.", icon: BriefcaseBusiness },
  { title: "Review shortlist", body: "Ranked candidates, each requirement backed by a quote from the resume.", icon: ClipboardCheck },
  { title: "Approve outreach", body: "Nothing sends until you approve the submittal or message.", icon: Send },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Welcome, Demo Recruiter"
        description="Here's where your candidate pool, job orders and approvals come together."
      />

      <section aria-label="Key numbers" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map((s) => (
          <Card key={s.label} className="gap-2">
            <CardHeader>
              <CardDescription className="flex items-center justify-between gap-2">
                <span>{s.label}</span>
                <s.icon className="size-4 text-muted-foreground" aria-hidden="true" />
              </CardDescription>
              <CardTitle className="text-3xl font-semibold tabular-nums">
                <span aria-hidden="true">–</span>
                <span className="sr-only">No data yet</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{s.caption}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Getting started</CardTitle>
          <CardDescription>The Placewise pipeline, from resume to approved outreach.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
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
    </div>
  );
}
