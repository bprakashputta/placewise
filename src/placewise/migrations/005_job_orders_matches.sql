-- 005: job orders (structured from recruiter notes) and match results (Blocks 4 + 6).
CREATE TABLE job_orders (
    id           BIGSERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    client       TEXT,
    raw_notes    TEXT NOT NULL,
    spec         JSONB NOT NULL,              -- structured requirements + clarifying questions
    status       TEXT NOT NULL DEFAULT 'open',  -- open | closed
    source_ref   TEXT UNIQUE,                 -- e.g. seed JO-01 (never used by the AI)
    created_by   BIGINT REFERENCES users (id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per (match run, candidate). The latest run per job order is the shortlist.
CREATE TABLE matches (
    id             BIGSERIAL PRIMARY KEY,
    job_order_id   BIGINT NOT NULL REFERENCES job_orders (id) ON DELETE CASCADE,
    run_id         TEXT NOT NULL,
    person_id      BIGINT NOT NULL REFERENCES people (id) ON DELETE CASCADE,
    resume_file_id BIGINT REFERENCES resume_files (id) ON DELETE SET NULL,
    score          REAL NOT NULL,             -- computed by code from verdicts and weights (0-100)
    recommendation TEXT NOT NULL,             -- submit | consider | pass
    verdicts       JSONB NOT NULL,            -- per requirement: verdict + verified evidence quote
    flags          TEXT[] NOT NULL DEFAULT '{}',
    summary        TEXT,
    retrieval_rank INT,
    status         TEXT NOT NULL DEFAULT 'proposed',  -- proposed | approved | rejected (recruiter decision)
    decided_by     BIGINT REFERENCES users (id),
    decided_at     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX matches_job_run_idx ON matches (job_order_id, run_id, score DESC);

CREATE TABLE match_runs (
    run_id        TEXT PRIMARY KEY,
    job_order_id  BIGINT NOT NULL REFERENCES job_orders (id) ON DELETE CASCADE,
    status        TEXT NOT NULL DEFAULT 'running',   -- running | done | failed
    filters       JSONB,
    relaxed       TEXT[] NOT NULL DEFAULT '{}',      -- hard filters loosened because too few candidates passed
    candidates    INT,
    cost_usd      NUMERIC(10, 5),
    error         TEXT,
    created_by    BIGINT REFERENCES users (id),
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);
