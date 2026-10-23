"use client";

import { useCallback, useEffect, useState } from "react";

// Typed client for the FastAPI routes in docs/api-contract.md. The browser only talks to
// same-origin /api/*, which next.config.ts rewrites to the api container.

export type Role = "admin" | "recruiter";
export type User = { username: string; display_name: string; role: Role };
export type Quality = "polished" | "flawed" | "unusable" | "adversarial";

export type Stats = {
  candidates: number;
  needs_attention: number;
  files_processed: number;
  ingest_jobs: Record<string, number>;
  by_quality: Record<string, number>;
  ai_spend_today_usd: number;
  ai_spend_total_usd: number;
  spend_cap_usd: number;
};

export type CandidateRow = {
  person_id: number;
  full_name: string;
  headline: string | null;
  discipline: string | null;
  subdiscipline: string | null;
  city: string | null;
  state: string | null;
  metro: string | null;
  years_experience: number | null;
  license_codes: string[];
  quality: Quality;
  quality_issues: string[];
  processed_at: string | null;
};

export type CandidateList = { total: number; limit: number; offset: number; items: CandidateRow[] };

export type Facets = {
  discipline: Record<string, number>;
  metro: Record<string, number>;
  quality: Record<string, number>;
  license: Record<string, number>;
  files: Record<string, number>;
};

export type NeedsAttention = {
  resume_file_id: number;
  filename: string;
  quality_issues: string[];
  reason: string;
  created_at: string;
};

export type Credential = { quote: string; key: string; state: string | null; status: string };
export type Job = {
  title: string | null;
  employer: string | null;
  location: string | null;
  start: string | null;
  end: string | null;
  highlights: string[];
};

export type CandidateDetail = {
  person_id: number;
  resume_file_id: number;
  filename: string;
  quality: Quality;
  quality_issues: string[];
  processed_at: string | null;
  years_experience: number | null;
  metro: string | null;
  license_codes: string[];
  software: string[];
  sectors: string[];
  findings: string[];
  validation_notes: string[];
  versions: {
    resume_file_id: number;
    filename: string;
    status: string;
    quality: Quality | null;
    is_current: boolean;
    created_at: string;
    processed_at: string | null;
  }[];
  profile: {
    full_name: string;
    headline: string | null;
    discipline: string | null;
    subdiscipline: string | null;
    summary: string | null;
    city: string | null;
    state: string | null;
    open_to_relocation: boolean | null;
    jobs: Job[];
    credentials: Credential[];
    software: string[];
    sectors: string[];
    education: { degree: string | null; school: string | null; year: string | null }[];
    writing_quality: { rating: string; issues: string[]; evidence: string[] } | null;
  };
};

export type UploadResult = { queued: boolean; job_id: number | null; sha256: string; message: string };
export type IngestJob = {
  id: number;
  status: "queued" | "running" | "done" | "duplicate" | "needs_attention" | "failed";
  attempts: number;
  error: string | null;
  result: { person_id?: number; [k: string]: unknown } | null;
  resume_file_id: number | null;
};

export type Costs = {
  spend_cap_usd: number;
  spent_today_usd: number;
  by_day: { day: string; calls: number; cost_usd: number }[];
  by_step_model: {
    step: string;
    model: string;
    calls: number;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  }[];
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** Send the browser to the login page, remembering where it was. */
export function redirectToLogin() {
  if (typeof window === "undefined" || window.location.pathname === "/login") return;
  const next = window.location.pathname + window.location.search;
  window.location.href = `/login?next=${encodeURIComponent(next)}`;
}

/**
 * fetch() for /api/* that parses JSON and throws ApiError on non-2xx. Any 401 (expired or missing
 * session) sends the user to /login: the client-side half of route protection. The API is the real
 * security check; this just keeps the UI from showing half-broken pages.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...init });
  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    redirectToLogin();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

type Entry<T> = { key: string; data?: T; error?: ApiError };

/**
 * Minimal data hook: fetches `path` whenever it changes (null = don't fetch). Keeps the previous
 * data while a new key loads so tables don't flash empty between filter changes.
 */
export function useApi<T>(path: string | null) {
  const [entry, setEntry] = useState<Entry<T> | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!path) return;
    let alive = true;
    const key = `${path}#${nonce}`;
    apiFetch<T>(path)
      .then((data) => alive && setEntry({ key, data }))
      .catch((e: unknown) =>
        alive &&
        setEntry({ key, error: e instanceof ApiError ? e : new ApiError(0, "Can't reach the API") }),
      );
    return () => {
      alive = false;
    };
  }, [path, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const current = entry?.key === `${path}#${nonce}`;
  return {
    data: entry?.data,
    error: current ? entry?.error : undefined,
    loading: path !== null && !current,
    reload,
  };
}
