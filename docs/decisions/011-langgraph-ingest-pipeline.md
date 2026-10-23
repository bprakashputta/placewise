# 011: LangGraph for the ingest pipeline

- **Status:** accepted
- **Date:** 2026-10-22

## Context
Each resume goes through several steps (read and dedupe, parse and screen, LLM extraction, code validation, embed and store), with two early exits (identical file, unreadable file). Paid calls must happen only when needed, and each resume should be easy to inspect end to end when something goes wrong. The architecture already uses LangGraph for the match graph and the agent (AGENTS.md).

## Decision
Build ingest as a LangGraph `StateGraph` (`src/placewise/ingest/graph.py`): `receive → parse_screen → extract → validate → embed_store`, with conditional edges `receive → duplicate` and `parse_screen → store_unusable`. The worker runs one graph invocation per job with `run_name = ingest:<source_ref>`, tags and job metadata, so **each resume is one LangSmith trace** with a span per node. File bytes never enter the state (only path and hash), so traces stay small.

## Alternatives considered
- **A plain async function:** less machinery, but routing would be hidden in if-statements, and traces would show one flat span plus the LLM call instead of named steps.
- **LCEL chains:** good for linear chains; awkward for branching to different end states.
- **A workflow engine (Temporal, Prefect):** durable step-level retries, but a heavy extra service; the queue already gives job-level retries ([ADR 010](010-postgres-job-queue-skip-locked.md)) and the extraction cache makes retries cheap ([ADR 014](014-extraction-cache-on-clean-text.md)).

## Tradeoffs and consequences
- **Gain:** routing **before** paid calls is explicit and tested (`test_duplicate_routes_before_any_parse_or_model_call`, `test_unusable_routes_to_needs_attention_without_model`); the diagram matches the code; one trace per resume in LangSmith; the same pattern as later graphs.
- **Give up:** a dependency and some ceremony for a mostly linear flow. No checkpointer is used for ingest: a retry restarts the graph from the top, and idempotency comes from the SHA check, the extraction cache and the single store transaction.
- **Revisit if:** ingest grows steps that need human input or long waits (then add a checkpointer), or the graph stays linear and LangGraph adds nothing.
