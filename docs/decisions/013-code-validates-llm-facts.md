# 013: Code validates the LLM's facts (quote verification, years from dates)

- **Status:** accepted
- **Date:** 2026-10-22

## Context
The extraction model can hallucinate a credential, attach the wrong state, or miscount experience. These fields are the hard filters recruiters rely on ("TX PE with 8+ years"). AGENTS.md's trust rule: the LLM must quote the resume, and code verifies.

## Decision
`src/placewise/ingest/validate.py` runs after every extraction and has the final say:
- **Credentials:** the model must return the exact `quote`; if the normalized quote (dashes, non-breaking spaces, whitespace) isn't in the resume text, the credential is **dropped** and a validation note is stored. States are kept only on state-issued licenses. `license_codes` includes only **active** credentials (not pursuing, exam scheduled, expired or OTHER).
- **Years of experience:** the model returns dates **as written**; code parses them, merges overlapping jobs, ignores gaps and computes the total. The model is never asked for a number of years.
- **Normalization:** state names → codes, city → metro, software and sectors → canonical names.
- **Quality label:** combines the code screen (security, readability) with the model's writing assessment by fixed rules.

## Alternatives considered
- **Trust the model's output:** simplest; one hallucinated PE becomes a wrong submittal.
- **Ask the model for years:** models are unreliable at date arithmetic with overlaps and gaps.
- **A second LLM pass to verify:** costs more and is still probabilistic; string matching is exact and free.

## Tradeoffs and consequences
- **Gain:** a credential in the database is always backed by text in the resume; years MAE 0.04 end to end; validation notes show recruiters what was dropped.
- **Give up:** a quote that the model paraphrased slightly is dropped even if the credential is real (false negatives). Unusual date formats can't be parsed and are ignored.
- **Revisit if:** evals on real resumes show many dropped-but-real credentials (then add fuzzy matching with a threshold).
