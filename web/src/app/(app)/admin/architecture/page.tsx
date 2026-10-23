import {
  BadgeCheck,
  Boxes,
  BrainCircuit,
  Calculator,
  CircleDollarSign,
  EyeOff,
  FileScan,
  FileText,
  Hand,
  Layers,
  ListFilter,
  MessagesSquare,
  Monitor,
  Network,
  Quote,
  Scale,
  Search,
  Server,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  UserCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import type { Metadata } from "next";
import { IconTile } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { EvalNumbers } from "../eval-numbers";
import { DiagramCard, type Diagram } from "./diagram-card";

export const metadata: Metadata = { title: "How it works" };

type Tone = "brand" | "info" | "success" | "warning" | "tamper";

const STEPS: { title: string; body: string; tech: string[]; icon: LucideIcon; tone: Tone }[] = [
  {
    title: "Resume intake",
    body: "PDF, DOCX and TXT files are parsed and screened for hidden text and prompt injection before any AI sees them (no AI, about 30 ms).",
    tech: ["Postgres job queue", "3 workers"],
    icon: FileScan,
    tone: "brand",
  },
  {
    title: "Structured profile",
    body: "Claude extracts the profile with evidence quotes. Code checks every license quote exists in the resume, computes years from dates and normalizes locations.",
    tech: ["Claude Sonnet 5.5", "LangGraph ingest graph"],
    icon: FileText,
    tone: "info",
  },
  {
    title: "Hybrid search",
    body: "Hard filters on code-checked fields (license + state, metro, years), then vector and keyword search, merged with Reciprocal Rank Fusion and reranked.",
    tech: ["voyage-4-large", "pgvector HNSW", "Postgres full-text", "rerank-3"],
    icon: Search,
    tone: "tamper",
  },
  {
    title: "Evidence-backed matching",
    body: "Code decides license, years, location and discipline; the LLM judges skills but must quote the resume (quotes verified). Code computes the score, and scoring is blind to identity.",
    tech: ["Claude Sonnet 5.5", "Blind scoring"],
    icon: Scale,
    tone: "warning",
  },
  {
    title: "Human approval",
    body: "The recruiter approves or rejects each candidate for submittal. Nothing is sent automatically.",
    tech: ["Recruiter in the loop"],
    icon: UserCheck,
    tone: "success",
  },
];

const ASK_ROUTES: { title: string; body: string; icon: LucideIcon; tone: Tone | "muted" }[] = [
  { title: "Greetings and help", body: "“Hi”, “thanks” and “what can you do?” are answered instantly by code: no search, $0.", icon: Hand, tone: "success" },
  { title: "Searches", body: "Real questions go through the RAG pipeline: understand → hybrid search → rerank → cited answer.", icon: Search, tone: "brand" },
  { title: "Follow-ups", body: "“Which of those have a PMP?” is narrowed to the candidates the previous answer cited.", icon: MessagesSquare, tone: "info" },
  { title: "Job-order chats", body: "A chat opened from a job order uses that job's structured requirements as the search plan.", icon: Workflow, tone: "warning" },
  { title: "Verified citations", body: "Every quote must appear word for word in the cited resume section, or code drops it.", icon: Quote, tone: "tamper" },
];

const ASK_DIAGRAMS: Diagram[] = [
  {
    src: "/diagrams/ask-conversation.svg",
    title: "How a chat message is routed",
    caption: "Each message is labeled first; only searches, follow-ups and job-order chats run a search.",
    alt: "Ask conversation flow: a message is routed to a greeting, help, search, follow-up, job-order or off-topic path; only search paths run the RAG graph.",
    width: 2830,
    height: 610,
  },
  {
    src: "/diagrams/rag-graph.svg",
    title: "The Ask search pipeline",
    caption: "Understand the question, retrieve with hybrid search, rerank, write a cited answer, verify the citations.",
    alt: "RAG graph: understand, retrieve (vector + keyword with RRF), rerank, answer, then a code citation check.",
    width: 2584,
    height: 383,
  },
];

const GALLERY: Diagram[] = [
  {
    src: "/diagrams/architecture.svg",
    title: "The system at a glance",
    caption: "Browser → web app → API; workers run the AI pipeline; Postgres stores everything.",
    alt: "Architecture: the browser talks to the web app, which forwards /api calls to the API; workers run the AI pipeline; Postgres stores everything.",
    width: 1678,
    height: 2030,
  },
  {
    src: "/diagrams/ingest-graph.svg",
    title: "What happens to one resume",
    caption: "Receive, parse and screen, extract, validate, embed and store; bad files exit early.",
    alt: "Ingest graph: receive, parse and screen, extract with Claude, validate, embed and store; duplicates and unreadable files exit early.",
    width: 1922,
    height: 392,
  },
  {
    src: "/diagrams/queue-lifecycle.svg",
    title: "How the work queue stays reliable",
    caption: "One job per file, claimed by one worker, bounded retries, paused at the spend cap.",
    alt: "Queue lifecycle: a job is queued, claimed by one worker, and ends as done, duplicate, needs attention or failed, with bounded retries.",
    width: 1205,
    height: 1342,
  },
  {
    src: "/diagrams/data-model.svg",
    title: "Resume data model",
    caption: "People, resume versions, profiles with evidence, searchable sections and the AI cost log.",
    alt: "Data model: people, resume files, profiles, resume sections with embeddings, ingest jobs, the extraction cache and the AI cost log.",
    width: 2247,
    height: 1628,
  },
  {
    src: "/diagrams/app-data-model.svg",
    title: "Portal data model",
    caption: "Portal data model: users, job orders, matching and Ask conversations.",
    alt: "Portal data model: users, job orders, match runs, matches, conversations and conversation messages.",
    width: 1832,
    height: 692,
  },
  ...ASK_DIAGRAMS,
];

const GALLERY_SPAN: Record<string, string> = {
  "/diagrams/architecture.svg": "xl:row-span-2",
  "/diagrams/app-data-model.svg": "sm:col-span-2",
};

const STACK: { group: string; icon: LucideIcon; items: { name: string; role: string }[] }[] = [
  {
    group: "AI orchestration",
    icon: Workflow,
    items: [
      { name: "LangGraph", role: "Ingest, Ask and match graphs" },
      { name: "LangChain", role: "Model calls and structured output" },
      { name: "LangSmith", role: "Tracing and evals" },
    ],
  },
  {
    group: "Models",
    icon: BrainCircuit,
    items: [
      { name: "Claude Sonnet 5.5", role: "Extraction, answers, scoring" },
      { name: "Claude Haiku 5.5", role: "Query understanding, routing" },
    ],
  },
  {
    group: "Search",
    icon: Layers,
    items: [
      { name: "Voyage voyage-4-large", role: "Embeddings" },
      { name: "Voyage rerank-3", role: "Reranking" },
      { name: "Postgres 17 + pgvector", role: "Vectors, full-text, everything else" },
    ],
  },
  {
    group: "Backend",
    icon: Server,
    items: [
      { name: "FastAPI", role: "Stateless API" },
      { name: "Python 3.12", role: "Workers and pipelines" },
      { name: "uv", role: "Dependencies" },
    ],
  },
  {
    group: "Frontend",
    icon: Monitor,
    items: [
      { name: "Next.js 16", role: "Portal (App Router)" },
      { name: "Tailwind", role: "Styling, light and dark" },
      { name: "shadcn/ui", role: "Components" },
    ],
  },
  {
    group: "Infra",
    icon: Boxes,
    items: [{ name: "Docker Compose", role: "db, api, 3 workers, web" }],
  },
];

const TRUST_RULES: { title: string; icon: LucideIcon }[] = [
  { title: "The LLM never has the final say on facts", icon: BadgeCheck },
  { title: "Every quote is verified by code", icon: Quote },
  { title: "Scores are computed by code", icon: Calculator },
  { title: "Hard filters, not AI guesses, for licenses", icon: ListFilter },
  { title: "Prompt-injection screening before any AI call", icon: ShieldAlert },
  { title: "Contact details never reach the AI search index", icon: EyeOff },
  { title: "Daily AI spend cap", icon: CircleDollarSign },
  { title: "Human approval before anything is sent", icon: UserCheck },
];

const TONE_DOT: Record<Tone, string> = {
  brand: "bg-brand",
  info: "bg-info",
  success: "bg-success",
  warning: "bg-warning",
  tamper: "bg-tamper",
};

function SectionHeading({ id, eyebrow, title, description }: { id: string; eyebrow: string; title: string; description?: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold tracking-wide text-brand uppercase">{eyebrow}</p>
      <h2 id={id} className="text-xl font-semibold tracking-[-0.018em]">
        {title}
      </h2>
      {description && <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden rounded-2xl border bg-card px-5 py-8 shadow-sm sm:px-10 sm:py-12">
      {/* Soft brand glow; decorative only. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-24 -right-24 size-80 rounded-full bg-brand/15 blur-3xl dark:bg-brand/20"
      />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-28 left-1/3 size-72 rounded-full bg-info/10 blur-3xl" />
      <div className="relative max-w-3xl space-y-4">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-[inset_0_1px_0_0_oklch(1_0_0/0.2)]">
            <Network className="size-4" aria-hidden="true" />
          </span>
          <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Admin · Walkthrough</span>
        </div>
        <h1 className="text-3xl leading-tight font-semibold tracking-[-0.025em] sm:text-4xl">How Placewise works</h1>
        <p className="text-base leading-relaxed text-muted-foreground sm:text-lg">
          An AI layer on top of a recruiting firm&apos;s ATS: resumes in, evidence-backed shortlists out. A human approves everything.
        </p>
        <ul className="flex flex-wrap gap-2 pt-1 text-xs font-medium">
          <li className="rounded-full bg-brand-soft px-2.5 py-1 text-brand-strong">Personal project, built this week</li>
          <li className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground ring-1 ring-border ring-inset">Synthetic data only</li>
          <li className="rounded-full bg-success-soft px-2.5 py-1 text-success-strong">Nothing sends without approval</li>
        </ul>
      </div>
    </section>
  );
}

function Pipeline() {
  return (
    <section aria-labelledby="pipeline-heading" className="space-y-5">
      <SectionHeading
        id="pipeline-heading"
        eyebrow="The pipeline"
        title="From resume to approved shortlist"
        description="Five steps. AI reads and judges; code checks the facts and does the math."
      />
      <ol className="relative grid gap-4 lg:grid-cols-5 lg:gap-3">
        {STEPS.map((s, i) => (
          <li key={s.title} className="relative flex gap-4 lg:flex-col lg:gap-0">
            {/* Connector: vertical on mobile (left rail), horizontal on desktop. */}
            {i < STEPS.length - 1 && (
              <>
                <span aria-hidden="true" className="absolute top-12 bottom-[-1rem] left-5 w-px bg-border lg:hidden" />
                <span
                  aria-hidden="true"
                  className="absolute top-5 left-[calc(50%+1.75rem)] hidden h-px w-[calc(100%-3.5rem+0.75rem)] bg-gradient-to-r from-border via-brand/40 to-border lg:block"
                />
              </>
            )}
            <div className="relative z-10 flex shrink-0 lg:justify-center lg:pb-3">
              <IconTile icon={s.icon} tone={s.tone} className="shadow-xs" />
            </div>
            <Card className="min-w-0 flex-1 gap-3 py-4">
              <CardHeader className="gap-1 px-4">
                <p className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                  <span className={cn("size-1.5 rounded-full", TONE_DOT[s.tone])} aria-hidden="true" /> Step {i + 1}
                </p>
                <CardTitle>{s.title}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-3 px-4">
                <p className="text-[13px] leading-relaxed text-muted-foreground">{s.body}</p>
                <ul className="mt-auto flex flex-wrap gap-1.5">
                  {s.tech.map((t) => (
                    <li key={t} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground/80 ring-1 ring-border ring-inset">
                      {t}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </li>
        ))}
      </ol>
    </section>
  );
}

function AskSection() {
  return (
    <section aria-labelledby="ask-heading" className="space-y-5">
      <SectionHeading
        id="ask-heading"
        eyebrow="Ask"
        title="Chat over your candidates"
        description="Each message is routed before any search, so small talk is instant and free, and follow-ups stay on the same candidates."
      />
      <Card>
        <CardContent className="space-y-6">
          <ul className="grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-5">
            {ASK_ROUTES.map((r) => (
              <li key={r.title} className="flex gap-3 xl:flex-col xl:gap-2">
                <IconTile icon={r.icon} tone={r.tone} size="sm" />
                <div className="min-w-0 space-y-0.5">
                  <p className="text-sm font-medium">{r.title}</p>
                  <p className="text-[13px] leading-relaxed text-muted-foreground">{r.body}</p>
                </div>
              </li>
            ))}
          </ul>
          <div className="grid gap-5 border-t pt-5">
            {ASK_DIAGRAMS.map((d) => (
              <DiagramCard key={d.src} d={d} variant="wide" />
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

function Gallery() {
  return (
    <section aria-labelledby="diagrams-heading" className="space-y-5">
      <SectionHeading id="diagrams-heading" eyebrow="Diagrams" title="Architecture diagrams" description="Click any diagram to open it full screen, zoom in and drag to pan." />
      {/* 7 diagrams: the tall architecture diagram spans two rows and the wide portal model two columns, so the grid has no gaps. */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-flow-dense xl:grid-cols-3">
        {GALLERY.map((d) => (
          <DiagramCard key={d.src} d={d} className={cn(GALLERY_SPAN[d.src])} />
        ))}
      </div>
    </section>
  );
}

function TechStack() {
  return (
    <section aria-labelledby="stack-heading" className="space-y-5">
      <SectionHeading id="stack-heading" eyebrow="Tech stack" title="What it's built with" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {STACK.map((g) => (
          <Card key={g.group} className="gap-3 py-4">
            <CardHeader className="flex flex-row items-center gap-2.5 px-4">
              <IconTile icon={g.icon} size="sm" tone="muted" />
              <CardTitle>{g.group}</CardTitle>
            </CardHeader>
            <CardContent className="px-4">
              <ul className="divide-y">
                {g.items.map((it) => (
                  <li key={it.name} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 py-2 first:pt-0 last:pb-0">
                    <span className="rounded-md bg-brand-soft px-2 py-0.5 text-xs font-semibold text-brand-strong">{it.name}</span>
                    <span className="text-xs text-muted-foreground">{it.role}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

function TrustRules() {
  return (
    <section aria-labelledby="trust-heading">
      <Card className="relative overflow-hidden">
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-brand-gradient" />
        <CardHeader className="flex flex-row items-center gap-3">
          <IconTile icon={ShieldCheck} tone="success" />
          <div className="space-y-0.5">
            <CardTitle id="trust-heading" className="text-base">
              Trust rules
            </CardTitle>
            <CardDescription>Where the AI is allowed to decide, and where code or a person does.</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {TRUST_RULES.map((r) => (
              <li key={r.title} className="flex items-start gap-2.5 rounded-lg bg-muted/50 px-3 py-2.5 ring-1 ring-border/60 ring-inset">
                <r.icon className="mt-0.5 size-4 shrink-0 text-success-strong" aria-hidden="true" />
                <span className="text-[13px] leading-snug font-medium">{r.title}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </section>
  );
}

export default function ArchitecturePage() {
  return (
    <div className="space-y-12">
      <Hero />
      <Pipeline />
      <AskSection />
      <TrustRules />
      <EvalNumbers headingId="numbers-heading" showLink />
      <Gallery />
      <TechStack />
      <p className="flex items-start gap-2 border-t pt-6 text-xs text-muted-foreground">
        <Sparkles className="mt-px size-3.5 shrink-0" aria-hidden="true" />
        A personal project built this week on synthetic data. Synthetic resumes are cleaner than real ones, so the numbers above are an optimistic upper
        bound, not production results.
      </p>
    </div>
  );
}

