import type { Metadata } from "next";
import { ArrowUp, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export const metadata: Metadata = { title: "Ask" };

const EXAMPLES = [
  "Who holds a Texas PE with drainage experience in DFW?",
  "Which licensed architects have healthcare projects over $50M?",
  "Find MEP engineers in Houston who know Revit and are LEED AP.",
];

export default function AskPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Ask"
        description="Questions about your candidate pool, answered with citations to the resumes."
      />
      <Card className="flex min-h-[28rem] flex-col justify-between gap-0 py-0">
        <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 text-center">
          <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
            <Sparkles className="size-5" aria-hidden="true" />
          </div>
          <h2 className="text-sm font-semibold">Ask anything about your candidates</h2>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            Every answer links back to the resume lines it came from. Available once resumes are ingested.
          </p>
          <ul className="mt-6 flex max-w-2xl flex-wrap justify-center gap-2" aria-label="Example questions">
            {EXAMPLES.map((q) => (
              <li key={q}>
                <Button variant="outline" size="sm" disabled className="h-auto rounded-full px-3 py-1.5 text-left whitespace-normal">
                  {q}
                </Button>
              </li>
            ))}
          </ul>
        </div>
        <form className="flex items-center gap-2 border-t p-3" aria-label="Ask a question">
          <label htmlFor="ask-input" className="sr-only">
            Your question
          </label>
          <Input id="ask-input" name="question" placeholder="Ask about your candidate pool…" disabled className="flex-1" />
          <Button type="submit" size="icon" disabled aria-label="Send question">
            <ArrowUp aria-hidden="true" />
          </Button>
        </form>
      </Card>
    </div>
  );
}
