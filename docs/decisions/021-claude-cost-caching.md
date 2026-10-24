# 021: Cut Claude spend with prompt caching and a LangChain response cache

- **Status:** accepted (owner, 2026-10-24: "make these changes", "use langchain wherever u need for optimization to cache stuff")
- **Date:** 2026-10-24

## Context
The owner's Claude credits drained faster than expected. The app's own log (`llm_calls`) explained ~$17.60, and its prices match the pricing page. The rest came from work the log never saw: the GitHub PR review action (22 runs, $6.89, billed to an API key), the Haiku-vs-Sonnet extraction eval (~$3.50) and synthetic-data generation (~$1–2). No call used prompt caching (0 cached tokens), and repeating the same request (re-running a match, asking the same question) paid full price every time.

## Decision
1. **PR reviews on the owner's Claude subscription:** `claude-review.yml` and `claude.yml` use `claude_code_oauth_token` (`CLAUDE_CODE_OAUTH_TOKEN`, from `claude setup-token`) instead of `ANTHROPIC_API_KEY`.
2. **Anthropic prompt caching through LangChain** (`llm_cost.cached_system`, a `cache_control` block on the system message). The cached prefix is the tool schema plus instructions:
   - **Match scoring, prompt v3:** the job order moved into the cached system prompt, so all candidates in a run share it. The first candidate is scored alone to write the cache; the rest then run in parallel and read it at 5% of the input price.
   - **Resume extraction:** shared across a batch of uploads.
   - **Ask answers:** shared across questions asked within 5 minutes.
3. **A LangChain response cache in Postgres** (`llm_cache.PostgresLLMCache`, a LangChain `BaseCache` passed as `ChatAnthropic(cache=...)`, migration 008). An identical request returns the stored response for $0.
   - **Used for:** match scoring, the job order builder, Ask answers, question understanding and routing.
   - **Never stores** a response that isn't a complete, valid answer: no tool call, cut off at `max_tokens`, or arguments that fail the expected Pydantic schema. A malformed answer can't be replayed (PR #7 review).
   - **Expiry and cleanup:** entries expire after `LLM_RESPONSE_CACHE_DAYS` (default 7; 0 turns it off). Expired rows are deleted at api startup and hourly by the worker.
   - **What it holds:** derived resume text. The request side includes the anonymized profile and job order; the stored response holds the model's quotes and summaries, and Ask answers include candidate names. It never holds contact details, which stay out of blind text and searchable sections. Rows aren't linked to a candidate, so deleting a resume leaves its cached responses until they expire (at most 7 days).
   - **Logging:** hits are logged as `status='cache_hit'` at $0.
4. **One cost function** (`llm_cost.usage_cost`) replaces four copies. It prices cache writes (1.25×), cache reads (0.05× Sonnet/Opus 5.5, 0.1× Haiku) and replayed responses ($0). `llm_calls.cached_tokens` records cache **reads**; cache writes are included in `cost_usd` but not counted separately.

## Measured (2026-10-24, on the owner's Mac copy)
| | Before | After |
|---|---|---|
| Matching eval, 15 job orders | $1.59 | **$1.27** (−20%), quality held: submit precision 97.5% (was 96.1%), 0 near misses, 69/70 strong in the fillable top 5s |
| Cost per scoring call | $0.0107 | $0.0082; cache hits 48% → ~74% with the warm-up call |
| Re-running a match on the same job order | ~$0.10, 15 s | **$0, 1.0 s**, identical scores and recommendations for every candidate |
| Same job-order notes structured twice | $0.0096, 4 s | **$0, 0.01 s** |

## Alternatives considered
- **`langchain-community` SQLAlchemyCache / RedisCache:** adds SQLAlchemy (or a Redis service) for one class; our Postgres pool already exists.
- **LangChain `InMemoryCache`:** lost on every deploy, and not shared between the api and the workers.
- **Semantic cache (similar questions reuse answers):** risks a wrong answer for a slightly different question; recruiters need exact answers.
- **Shorter outputs / Haiku for extraction:** output is ~two-thirds of Sonnet spend, so these save more, but they risk quality. Left for a measured follow-up (the eval showed Haiku at 96% vs Sonnet 100% on licenses).

## Tradeoffs and consequences
- **Gain:** about 20% off match runs, free and instant repeats, and reviews no longer use API credits.
- **Give up:** match runs take one extra call's latency (~5 s) for the warm-up. A cache write costs 25% more on the shared prefix when nothing reuses it within 5 minutes (a single isolated question or upload), which is negligible at these sizes.
- **Repeats are deterministic:** re-running an identical match returns the same verdicts. Change the job order, or wait for expiry, to get a fresh judgment.
- **Revisit if:** recruiters want a "re-score from scratch" button (bypass the cache for that run), or output-token savings become the priority.
