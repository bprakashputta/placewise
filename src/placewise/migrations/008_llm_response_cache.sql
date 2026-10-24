-- 008: LangChain response cache (src/placewise/llm_cache.py). An identical Claude request (same model,
-- settings, tool schema and messages) returns the stored response for $0 instead of calling the API.
-- Keys are SHA-256 hashes of LangChain's prompt and llm strings; entries expire after
-- LLM_RESPONSE_CACHE_DAYS (default 30). A prompt version change produces new keys automatically.
CREATE TABLE IF NOT EXISTS llm_response_cache (
    prompt_key  text NOT NULL,
    llm_key     text NOT NULL,
    value       text NOT NULL,              -- langchain_core.load.dumps of the generations
    hits        integer NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    last_hit_at timestamptz,
    PRIMARY KEY (prompt_key, llm_key)
);
CREATE INDEX IF NOT EXISTS llm_response_cache_created ON llm_response_cache (created_at);
