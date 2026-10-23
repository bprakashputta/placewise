import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

// Hard-coded eval results, shown on /admin/architecture and /admin/evals. They come from the last
// eval runs (src/placewise/evals/*), recorded in docs/modules/ingest.md, docs/modules/rag.md and ADR 018.
// They are fixed numbers, not live ones: rerun the commands below to refresh them.
export const EVAL_MEASURED = "Measured on the synthetic dataset (Oct 23)";
export const EVAL_ANSWER_KEY_NOTE = "The generator's answer key is never visible to the app.";

export type Tone = "brand" | "success" | "info" | "warning" | "tamper";

/** The headline numbers shown in the "Key numbers" strip. */
export const EVAL_NUMBERS: { value: string; label: string; note: string; tone: Tone }[] = [
  { value: "597/597", label: "Files routed correctly", note: "PDF, DOCX and TXT, end to end", tone: "brand" },
  { value: "99.7%", label: "Licenses exact", note: "License type and state both correct", tone: "success" },
  { value: "89%", label: "Search recall@10", note: "Known strong fits in the top 10", tone: "info" },
  { value: "97.6%", label: "Submit precision", note: "Of 125 candidates suggested to submit", tone: "success" },
  { value: "34/34", label: "Chat messages routed", note: "Greetings, searches, follow-ups, off-topic", tone: "tamper" },
  { value: "$0.02", label: "Per resume", note: "Extraction with Claude Sonnet 5.5", tone: "warning" },
];

export type Metric = { value: string; label: string };

export type EvalResult = {
  id: string;
  title: string;
  headline: Metric;
  metrics: Metric[];
  meaning: string;
  measured: string;
  command?: string;
};

export const EVAL_RESULTS: EvalResult[] = [
  {
    id: "ingest",
    title: "Resume ingest",
    headline: { value: "597/597", label: "files routed to the right outcome" },
    metrics: [
      { value: "99.7%", label: "License type + state exact" },
      { value: "563/563", label: "People matched (several resumes, one person)" },
      { value: "100%", label: "Unreadable & tampered caught, before any AI call" },
      { value: "88% / 92%", label: "“Needs cleanup” precision / recall" },
    ],
    meaning:
      "Every resume ends up in the right place, credentials are read almost perfectly, and bad files are stopped before Claude ever sees them. About $0.02 per resume ($12.23 for all 597).",
    measured:
      "All 597 synthetic files are ingested through the real queue and workers, then each stored profile is compared field by field with the generator's answer key.",
    command: "python -m placewise.evals.ingest_db",
  },
  {
    id: "retrieval",
    title: "Search (retrieval)",
    headline: { value: "89%", label: "recall@10" },
    metrics: [
      { value: "98%", label: "precision@10" },
      { value: "1.00", label: "MRR (a strong fit is ranked first)" },
    ],
    meaning:
      "For each job order, almost all of the known strong candidates show up in the first 10 results, and nearly everything in the top 10 is relevant.",
    measured:
      "Each job order's requirements become a query; the known strong fits from the answer key are the relevant set. Each search layer is also measured on its own (chart).",
    command: "python -m placewise.evals.retrieval",
  },
  {
    id: "ask",
    title: "Ask answers",
    headline: { value: "21/21", label: "quotes verified against the cited resume" },
    metrics: [
      { value: "~10–15 s", label: "Per question" },
      { value: "~$0.03", label: "Per question" },
      { value: "0", label: "Emails or phones leaked to an injection question" },
      { value: "2", label: "Questions checked, every citation compared" },
    ],
    meaning:
      "Every claim in an answer points to a resume line that really says it. Citations that don't match word for word are dropped by code before you see the answer.",
    measured:
      "A QA pass checked every citation in 2 answers against the resume section it cites, and asked a prompt-injection question that tried to pull contact details.",
  },
  {
    id: "matching",
    title: "Matching",
    headline: { value: "97.6%", label: "“submit” precision (of 125 suggested)" },
    metrics: [
      { value: "0", label: "Near misses suggested as submit" },
      { value: "92.0%", label: "precision@5, strong (94.7% strong or partial)" },
      { value: "0", label: "Submits for the unfillable job order" },
      { value: "$1.59", label: "For all 15 job orders" },
    ],
    meaning:
      "When Placewise says “submit”, the candidate is almost always a real fit, and it doesn't push near misses or invent a fit for a role nobody can fill.",
    measured:
      "A match is run for each of the 15 synthetic job orders, and every shortlist is graded against the answer key (strong, partial, near miss, no fit).",
    command: "python -m placewise.evals.matching",
  },
  {
    id: "routing",
    title: "Chat routing",
    headline: { value: "34/34", label: "messages routed correctly" },
    metrics: [
      { value: "7", label: "Message types (greetings, help, searches, follow-ups, job orders, off-topic, gibberish)" },
      { value: "$0.007", label: "For the whole eval" },
    ],
    meaning: "A “hi” gets a quick reply instead of a search, and a follow-up like “which of those have a PMP?” stays on the same candidates.",
    measured: "34 labeled messages, including mixed “hi + request” messages, follow-ups with history and injection attempts, each checked against its expected route.",
    command: "python -m placewise.evals.ask_routing",
  },
  {
    id: "tests",
    title: "Automated tests",
    headline: { value: "335", label: "tests passing" },
    metrics: [{ value: "Unit + API", label: "Seed data, ingest, search, Ask, matching, auth and API routes" }],
    meaning: "Every change runs the full suite in CI before it can be merged.",
    measured: "pytest inside the api container, plus web lint and build, on every pull request.",
    command: "pytest -q tests",
  },
];

/** Retrieval ablation: what each layer of the search adds (recall@10). */
export const RETRIEVAL_ABLATION = [
  { step: "Vector only", recall: 48 },
  { step: "+ Hard filters", recall: 84 },
  { step: "+ Keyword + rerank", recall: 89 },
];

const TONE_TEXT: Record<Tone, string> = {
  brand: "text-brand",
  success: "text-success-strong",
  info: "text-info-strong",
  warning: "text-warning-strong",
  tamper: "text-tamper-strong",
};
const TONE_BAR: Record<Tone, string> = {
  brand: "bg-brand",
  success: "bg-success",
  info: "bg-info",
  warning: "bg-warning",
  tamper: "bg-tamper",
};

/** "Key numbers" strip: one row of headline results, with an optional link to the Evals page. */
export function EvalNumbers({ headingId, title = "Key numbers", showLink = false }: { headingId: string; title?: string; showLink?: boolean }) {
  return (
    <section aria-labelledby={headingId} className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-1">
        <div>
          <h2 id={headingId} className="text-[15px] font-semibold tracking-[-0.01em]">
            {title}
          </h2>
          <p className="text-xs text-muted-foreground">{EVAL_MEASURED}</p>
        </div>
        {showLink && (
          <Link
            href="/admin/evals"
            className="group/link inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
          >
            See how each is measured
            <ArrowRight className="size-3.5 transition-transform duration-150 group-hover/link:translate-x-0.5" aria-hidden="true" />
          </Link>
        )}
      </div>
      <div className="grid grid-cols-2 overflow-hidden rounded-xl border bg-card shadow-xs md:grid-cols-3 xl:grid-cols-6">
        {EVAL_NUMBERS.map((n) => (
          <div key={n.label} className="relative -mt-px -ml-px border-t border-l p-4">
            <span className={cn("absolute top-0 left-4 h-0.5 w-6 rounded-full", TONE_BAR[n.tone])} aria-hidden="true" />
            <p className={cn("text-2xl font-semibold tracking-[-0.02em] tabular-nums", TONE_TEXT[n.tone])}>{n.value}</p>
            <p className="mt-1 text-sm font-medium">{n.label}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{n.note}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
