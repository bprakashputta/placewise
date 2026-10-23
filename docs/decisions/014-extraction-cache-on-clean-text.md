# 014: Extraction cache keyed on the clean text

- **Status:** accepted
- **Date:** 2026-10-22

## Context
During the first ingest runs, Voyage rate limits made jobs fail after the Claude extraction had already succeeded. The worker retried the whole graph, so Claude was called again: about $0.26 wasted (build log, 2026-10-22).

## Decision
Migration 002 adds `extraction_cache (sha256, model, prompt_version) → profile`. The key is **`sha256(clean_text)`**: the hash of the exact text the model reads (after parsing and injection stripping), plus the model id and the prompt version. The `extract` node checks the cache first (no spend check, $0 cost) and writes to it after a successful call. `POST /api/dev/ingest/reset` keeps the cache.

## Alternatives considered
- **Key on the file hash:** the first version. Rejected because a parser or screen change would silently reuse an extraction made from different text.
- **Step-level checkpoints (LangGraph checkpointer):** would resume after the failed step, but adds checkpoint tables and doesn't help a re-ingest after a reset.
- **No cache, rely on retries being rare:** retries are exactly when paid calls repeat.

## Tradeoffs and consequences
- **Gain:** retries and full re-ingests cost $0 in LLM spend (the re-ingest after the person-matching fix cost $0.11, only for 5 resumes that predated the cache). Changing the model, prompt version, parser or screen naturally misses the cache.
- **Give up:** a small table, and a deliberate prompt edit **must** bump the prompt version, or the old extractions are reused.
- **Revisit if:** non-deterministic re-extraction is wanted (for example sampling for evals); evals call `extract()` directly and bypass the cache.
