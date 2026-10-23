"""Postgres + pgvector. One database holds structured fields, full text, vectors and logs,
so hard filters, keyword search and vector search can run in a single SQL query."""
from __future__ import annotations

from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from .config import get_settings

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS candidates (
    id               SERIAL PRIMARY KEY,
    source_file      TEXT,
    content_hash     TEXT UNIQUE NOT NULL,          -- idempotency: same resume twice = one row
    raw_text         TEXT NOT NULL,
    profile          JSONB NOT NULL,
    full_name        TEXT,
    metro            TEXT,
    discipline       TEXT,
    years_experience REAL,
    open_to_relocation BOOLEAN,
    license_keys     TEXT[] DEFAULT '{}',           -- e.g. {PE, LEED_AP}
    license_codes    TEXT[] DEFAULT '{}',           -- e.g. {PE:TX, PE:OK}
    software         TEXT[] DEFAULT '{}',
    sectors          TEXT[] DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id            SERIAL PRIMARY KEY,
    candidate_id  INT REFERENCES candidates(id) ON DELETE CASCADE,
    chunk_index   INT,
    section       TEXT,
    text          TEXT NOT NULL,
    embedding     vector({dim}),
    tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS candidates_license_keys ON candidates USING gin (license_keys);

CREATE TABLE IF NOT EXISTS job_orders (
    id            SERIAL PRIMARY KEY,
    content_hash  TEXT UNIQUE NOT NULL,
    raw_notes     TEXT NOT NULL,
    job           JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS matches (
    id             SERIAL PRIMARY KEY,
    run_id         TEXT NOT NULL,
    job_order_id   INT REFERENCES job_orders(id) ON DELETE CASCADE,
    candidate_id   INT REFERENCES candidates(id) ON DELETE CASCADE,
    score          REAL,
    recommendation TEXT,
    result         JSONB,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outreach (
    id            SERIAL PRIMARY KEY,
    kind          TEXT NOT NULL,                  -- candidate | client_pitch
    job_order_id  INT REFERENCES job_orders(id) ON DELETE CASCADE,
    candidate_id  INT REFERENCES candidates(id) ON DELETE CASCADE,
    subject       TEXT,
    body          TEXT,
    status        TEXT DEFAULT 'pending_approval', -- nothing is ever sent automatically
    checks        JSONB,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id             SERIAL PRIMARY KEY,
    run_id         TEXT,
    step           TEXT,
    provider       TEXT,
    model          TEXT,
    prompt_version TEXT,
    input_tokens   INT,
    output_tokens  INT,
    cached_tokens  INT,
    latency_ms     INT,
    cost_usd       NUMERIC(10,6),
    attempt        INT,
    status         TEXT,      -- ok | invalid_output | error
    error          TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dead_letters (
    id          SERIAL PRIMARY KEY,
    kind        TEXT,
    payload     JSONB,
    error       TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
"""


def connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().database_url, row_factory=dict_row, autocommit=True)
    register_vector(conn)
    return conn


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db(reset: bool = False) -> None:
    dim = get_settings().embed_dim
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        if reset:
            conn.execute(
                "DROP TABLE IF EXISTS dead_letters, llm_calls, outreach, matches, job_orders, chunks, candidates CASCADE"
            )
        conn.execute(SCHEMA.replace("{dim}", str(dim)))
