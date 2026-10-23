-- 001: core schema for ingest (Block 2).
-- One Postgres holds people, resume versions, extracted profiles, searchable chunks (vector +
-- full-text), the job queue and LLM call logs, so filters and search can run in one query.

CREATE EXTENSION IF NOT EXISTS vector;

-- A person can have several resume versions (resubmissions, updates).
CREATE TABLE people (
    id            BIGSERIAL PRIMARY KEY,
    display_name  TEXT,
    email_norm    TEXT,
    phone_norm    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX people_email_uq ON people (email_norm) WHERE email_norm IS NOT NULL;
CREATE INDEX people_phone_idx ON people (phone_norm) WHERE phone_norm IS NOT NULL;

-- Every file we receive. The sha256 makes ingest idempotent: the same bytes are never processed twice.
CREATE TABLE resume_files (
    id              BIGSERIAL PRIMARY KEY,
    person_id       BIGINT REFERENCES people (id) ON DELETE SET NULL,
    sha256          TEXT NOT NULL UNIQUE,
    filename        TEXT NOT NULL,
    media_type      TEXT,
    size_bytes      INT,
    source          TEXT NOT NULL,          -- upload | seed | n8n | ...
    source_ref      TEXT,                   -- e.g. the seed candidate folder; never used by the AI
    storage_path    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'received',   -- received | processed | needs_attention | duplicate
    quality         TEXT,                   -- polished | flawed | unusable | adversarial (as DETECTED)
    quality_issues  TEXT[] NOT NULL DEFAULT '{}',
    parse_info      JSONB,
    error           TEXT,
    is_current      BOOLEAN NOT NULL DEFAULT FALSE,     -- the person's latest processed version
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ
);
CREATE INDEX resume_files_person_idx ON resume_files (person_id);
CREATE UNIQUE INDEX resume_files_one_current ON resume_files (person_id) WHERE is_current;

-- The validated, structured profile extracted from one resume version.
CREATE TABLE profiles (
    resume_file_id     BIGINT PRIMARY KEY REFERENCES resume_files (id) ON DELETE CASCADE,
    person_id          BIGINT REFERENCES people (id) ON DELETE CASCADE,
    data               JSONB NOT NULL,
    full_name          TEXT,
    headline           TEXT,
    discipline         TEXT,
    subdiscipline      TEXT,
    city               TEXT,
    state              TEXT,
    metro              TEXT,
    open_to_relocation BOOLEAN,
    years_experience   REAL,
    license_codes      TEXT[] NOT NULL DEFAULT '{}',  -- e.g. {PE:TX, LEED_AP}
    software           TEXT[] NOT NULL DEFAULT '{}',
    sectors            TEXT[] NOT NULL DEFAULT '{}',
    blind_text         TEXT,                          -- identity removed, for unbiased scoring later
    model              TEXT,
    prompt_version     INT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX profiles_license_gin ON profiles USING gin (license_codes);
CREATE INDEX profiles_software_gin ON profiles USING gin (software);
CREATE INDEX profiles_sectors_gin ON profiles USING gin (sectors);
CREATE INDEX profiles_filter_idx ON profiles (discipline, metro, years_experience);

-- Searchable sections: one chunk per section (each job, skills, credentials, ...).
CREATE TABLE chunks (
    id              BIGSERIAL PRIMARY KEY,
    resume_file_id  BIGINT NOT NULL REFERENCES resume_files (id) ON DELETE CASCADE,
    person_id       BIGINT REFERENCES people (id) ON DELETE CASCADE,
    section         TEXT NOT NULL,          -- summary | job | skills | credentials | education | projects
    ordinal         INT NOT NULL,
    content         TEXT NOT NULL,          -- what is embedded and shown as a citation
    embedding       vector(1024),
    tsv             tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX chunks_file_idx ON chunks (resume_file_id);

-- Work queue. Workers claim jobs with FOR UPDATE SKIP LOCKED, so jobs are never processed twice
-- concurrently, and more workers can be added just by scaling the container.
CREATE TABLE ingest_jobs (
    id              BIGSERIAL PRIMARY KEY,
    kind            TEXT NOT NULL DEFAULT 'resume',
    source          TEXT NOT NULL,
    source_ref      TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'queued',  -- queued | running | done | duplicate | needs_attention | failed
    attempts        INT NOT NULL DEFAULT 0,
    max_attempts    INT NOT NULL DEFAULT 3,
    not_before      TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_by       TEXT,
    locked_at       TIMESTAMPTZ,
    resume_file_id  BIGINT REFERENCES resume_files (id) ON DELETE SET NULL,
    error           TEXT,
    result          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ingest_jobs_source_uq ON ingest_jobs (source, source_ref);
CREATE INDEX ingest_jobs_ready_idx ON ingest_jobs (not_before) WHERE status = 'queued';

-- Every LLM call: tokens, latency, cost, status. The source for cost dashboards and spend caps.
CREATE TABLE llm_calls (
    id              BIGSERIAL PRIMARY KEY,
    run_ref         TEXT,
    step            TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt_version  INT,
    input_tokens    INT NOT NULL DEFAULT 0,
    output_tokens   INT NOT NULL DEFAULT 0,
    cached_tokens   INT NOT NULL DEFAULT 0,
    latency_ms      INT,
    cost_usd        NUMERIC(10, 6),
    status          TEXT NOT NULL,          -- ok | invalid_output | error
    error           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX llm_calls_created_idx ON llm_calls (created_at);

-- Convenience view: one row per person with their current profile.
CREATE VIEW current_candidates AS
SELECT p.id AS person_id, rf.id AS resume_file_id, rf.filename, rf.quality, rf.quality_issues,
       rf.processed_at, pr.full_name, pr.headline, pr.discipline, pr.subdiscipline, pr.city, pr.state,
       pr.metro, pr.open_to_relocation, pr.years_experience, pr.license_codes, pr.software, pr.sectors
FROM people p
JOIN resume_files rf ON rf.person_id = p.id AND rf.is_current
LEFT JOIN profiles pr ON pr.resume_file_id = rf.id;
