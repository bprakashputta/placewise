# 009: Haiku as the resume writer, separate from the reader model

- **Status:** accepted
- **Date:** 2026-10-22

## Context
About 600 resumes had to be written, rewritten when the prompt improved, and fact-checked with retries. Two concerns:
1. **Bias:** if the same model writes the resumes and later extracts profiles from them, it reads its own style and vocabulary, and extraction looks easier than on human resumes.
2. **Cost:** several full rewrites were expected during prompt iteration (v1 → v5).

## Decision
Use **Claude Haiku 5.5** (`claude-haiku-5-5`, set in the prompt YAML) as the writer for resumes and job-order notes. The planned reader for ingest and matching is **Claude Sonnet 5.5** (Block 2+), a different model.

Bias is reduced further by things that don't depend on the model:
- credential phrasing, date formats, layouts, bullet symbols, typos and unreadable/adversarial files come from **code**;
- the answer key is computed from **facts**, not text;
- dev/test split by person;
- truth never mounted into the api ([ADR 008](008-answer-key-isolation.md)).

## Alternatives considered
- **Sonnet as the writer:** better prose, but the same model as the planned reader (more bias) and higher cost per rewrite.
- **Opus as the writer:** best prose, highest cost; deferred to Resume Generator v2 (PLAN item 11), where it would still differ from the reader.
- **A non-Anthropic writer:** would maximize model diversity but adds a second provider, key and SDK for test data only.

## Tradeoffs and consequences
- **Gain:** cheap iteration. A full rewrite cost about $0.64, the 97 targeted resumes about $0.12, samples and notes a few cents (Haiku 5.5 at $0.10/$0.50 per million tokens). Reader and writer differ.
- **Give up:** Haiku's prose is simpler and more uniform than real resumes; it needed prompt rules and fact-check retries (e.g. it kept adding software not in the facts). Haiku and Sonnet are still the same model family, so some shared style remains. Synthetic accuracy stays an **optimistic upper bound**.
- **Revisit if:** evals show suspiciously high extraction accuracy on synthetic data, or Resume Generator v2 moves the writer to Opus.
