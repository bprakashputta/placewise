import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Hard-coded eval results, shown on /admin/architecture and /admin/evals.
// From docs/modules/ingest.md (evals/ingest_db.py and evals/parse_screen.py, all 597 files).
export const EVAL_MEASURED = "Measured on the synthetic dataset (Oct 23)";

const EVAL_NUMBERS = [
  { value: "597", label: "Resumes ingested", note: "PDF, DOCX and TXT, end to end" },
  { value: "99.7%", label: "Licenses exact", note: "License type and state both correct" },
  { value: "563/563", label: "People matched", note: "Multiple resumes linked to one person" },
  { value: "100%", label: "Unreadable & tampered caught", note: "Precision and recall, before any AI call" },
  { value: "$0.02", label: "Per resume", note: "Claude Sonnet extraction; embeddings free tier" },
];

export function EvalNumbers({ headingId, title = "Key numbers" }: { headingId: string; title?: string }) {
  return (
    <section aria-labelledby={headingId} className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={headingId} className="text-sm font-semibold">
          {title}
        </h2>
        <p className="text-xs text-muted-foreground">{EVAL_MEASURED}</p>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        {EVAL_NUMBERS.map((n) => (
          <Card key={n.label} className="gap-1 py-4">
            <CardHeader className="px-4">
              <CardTitle className="text-2xl font-semibold tabular-nums">{n.value}</CardTitle>
              <CardDescription className="text-sm font-medium text-foreground">{n.label}</CardDescription>
            </CardHeader>
            <CardContent className="px-4">
              <p className="text-xs text-muted-foreground">{n.note}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
