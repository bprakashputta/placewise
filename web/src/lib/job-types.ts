import type { Quality } from "@/lib/api";

// Job orders + matching, Blocks 4 + 6 (docs/api-contract.md on block/04-matching).
export type JobOrderRow = {
  id: number;
  title: string;
  client: string | null;
  status: string;
  created_at: string;
  metro: string | null;
  discipline: string | null;
  last_run_id: string | null;
  last_run_status: "running" | "done" | "failed" | null;
  last_run_at: string | null;
  submit_count: number | null;
};

export type Requirement = {
  text: string;
  kind: string;
  priority: "must" | "nice";
  key: string | null;
  state: string | null;
  value: string | null;
};

export type JobSpec = {
  title: string;
  client: string | null;
  city: string | null;
  metro: string | null;
  work_mode: string | null;
  employment_type: string | null;
  salary: string | null;
  discipline: string | null;
  subdiscipline: string | null;
  min_years: number | null;
  requirements: Requirement[];
  open_questions: string[];
};

export type JobOrder = {
  id: number;
  title: string;
  client: string | null;
  raw_notes: string;
  spec: JobSpec;
  status: string;
  created_at: string;
  cost_usd?: number;
};

export type Verdict = {
  requirement: string;
  verdict: "met" | "partial" | "not_met" | "unknown";
  evidence: string | null;
  note: string | null;
};

export type MatchDecision = "proposed" | "approved" | "rejected";

export type Match = {
  id: number;
  person_id: number;
  resume_file_id: number;
  score: number;
  recommendation: "submit" | "consider" | "pass";
  verdicts: Verdict[];
  flags: string[];
  summary: string | null;
  retrieval_rank: number | null;
  status: MatchDecision;
  full_name: string;
  headline: string | null;
  metro: string | null;
  years_experience: number | null;
  license_codes: string[];
  quality: Quality;
};

export type MatchRun = {
  run_id: string;
  status: "running" | "done" | "failed";
  filters: Record<string, unknown>;
  relaxed: string[];
  candidates: number | null;
  cost_usd: number | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type MatchesResponse = { run: MatchRun | null; matches: Match[] };
