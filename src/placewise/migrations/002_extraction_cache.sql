-- 002: cache LLM extractions by file hash + model + prompt version.
-- A retry (e.g. after an embedding rate limit) reuses the already-paid extraction instead of calling
-- the model again. Changing the model or prompt version naturally misses the cache.
CREATE TABLE extraction_cache (
    sha256          TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt_version  INT NOT NULL,
    profile         JSONB NOT NULL,
    cost_usd        NUMERIC(10, 6),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (sha256, model, prompt_version)
);
