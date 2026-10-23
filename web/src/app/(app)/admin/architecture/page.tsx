import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DiagramCard, type Diagram } from "./diagram-card";

export const metadata: Metadata = { title: "How it works" };

// Numbers from docs/modules/ingest.md (evals/ingest_db.py and evals/parse_screen.py, all 597 files).
const NUMBERS = [
  { value: "597", label: "Resumes ingested", note: "PDF, DOCX and TXT, end to end" },
  { value: "99.7%", label: "Licenses exact", note: "License type and state both correct" },
  { value: "563/563", label: "People matched", note: "Multiple resumes linked to one person" },
  { value: "100%", label: "Unusable & adversarial caught", note: "Precision and recall, before any AI call" },
  { value: "$0.02", label: "Per resume", note: "Claude Sonnet extraction; embeddings free tier" },
];

const DIAGRAMS: Diagram[] = [
  {
    step: 1,
    src: "/diagrams/architecture.svg",
    title: "The system at a glance",
    alt: "Architecture: the browser talks to the web app, which forwards /api calls to the API; workers run the AI pipeline; Postgres stores everything.",
    width: 1391,
    height: 1850,
    points: [
      "The browser only ever talks to the web app. It forwards /api requests to the API, so nothing else is exposed.",
      "The API is stateless: it checks your session, answers questions from the database and puts new work on a queue.",
      "Workers do the slow AI work in the background, so uploads return instantly and more workers can be added when volume grows.",
      "Postgres (with pgvector) is the single store: people, resumes, profiles, searchable chunks, the job queue and every AI cost.",
      "Claude reads resumes, Voyage turns sections into vectors for search, and LangSmith records a trace of every run.",
    ],
  },
  {
    step: 2,
    src: "/diagrams/ingest-graph.svg",
    title: "What happens to one resume",
    alt: "Ingest graph: receive, parse and screen, extract with Claude, validate, embed and store; duplicates and unusable files exit early.",
    width: 1922,
    height: 392,
    points: [
      "Receive: the file is fingerprinted. An identical file that was already processed stops here and costs nothing.",
      "Parse and screen (no AI, about 30 ms): text is pulled out, and hidden text or instructions aimed at AI systems are detected and removed. Scanned or corrupt files go to Needs attention.",
      "Extract: Claude turns the clean text into a structured profile and must quote the resume for every credential. Results are cached, so a retry never pays twice.",
      "Validate: code checks each quote really appears in the resume (unverifiable credentials are dropped), computes years from dates and labels the resume's quality.",
      "Embed and store: sections become searchable vectors and the profile is saved in one transaction, linked to the right person.",
    ],
  },
  {
    step: 3,
    src: "/diagrams/queue-lifecycle.svg",
    title: "How the work queue stays reliable",
    alt: "Queue lifecycle: a job is queued, claimed by one worker, and ends as done, duplicate, needs attention or failed, with bounded retries.",
    width: 1205,
    height: 1342,
    points: [
      "Every upload becomes one job. Submitting the same file twice doesn't create a second job.",
      "Workers claim jobs with a database lock, so two workers never process the same resume.",
      "Temporary errors are retried a limited number of times; a crashed worker's job is picked up again automatically.",
      "When the daily AI spend cap is reached, jobs pause instead of failing, and resume later.",
      "Each job ends in one clear state: done, duplicate, needs attention or failed (with the error kept for an admin).",
    ],
  },
  {
    step: 4,
    src: "/diagrams/data-model.svg",
    title: "How the data is organized",
    alt: "Data model: people, resume files, profiles, section chunks with embeddings, ingest jobs, the extraction cache and the AI cost log.",
    width: 2247,
    height: 1628,
    points: [
      "A person can have several resume files over time; the latest processed one is the current profile, older ones stay as versions.",
      "Each profile keeps the evidence: credential quotes, findings from screening and validation notes.",
      "Resumes are split into sections (chunks) with vectors and full-text indexes, which power search and matching later.",
      "Contact details never go into the searchable chunks, and scoring will use a blind version without names.",
      "Every AI call is logged with tokens and cost, which feeds the AI costs page and the spend cap.",
    ],
  },
];

export default function ArchitecturePage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="How it works"
        description="A walk through Placewise: how a resume becomes a trustworthy, searchable profile."
      />

      <section aria-labelledby="numbers-heading" className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="numbers-heading" className="text-sm font-semibold">
            Key numbers
          </h2>
          <p className="text-xs text-muted-foreground">Measured on the synthetic dataset</p>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
          {NUMBERS.map((n) => (
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

      <div className="space-y-6">
        {DIAGRAMS.map((d) => (
          <DiagramCard key={d.src} d={d} />
        ))}
      </div>

      <p className="text-xs text-muted-foreground">
        Synthetic resumes are cleaner than real ones, so these numbers are an optimistic upper bound.
      </p>
    </div>
  );
}
