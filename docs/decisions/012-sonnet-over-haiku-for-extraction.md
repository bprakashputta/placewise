# 012: Claude Sonnet 5.5 over Haiku 5.5 for profile extraction, decided by eval

- **Status:** accepted
- **Date:** 2026-10-22

## Context
AGENTS.md says to use Haiku only where evals show equal quality. Extraction errors are costly in recruiting: a wrong or stateless license (for example a stateless "PE" instead of an Arkansas PE) can cause a bad submittal. Haiku is about 20× cheaper per resume.

## Decision
Use **Claude Sonnet 5.5** (`claude-sonnet-5-5`, set in `prompts/ingest_extract_profile.v1.yaml`) for extraction. The owner decided after an eval on the **dev split (167 resumes; 164 extracted, 3 correctly routed as unusable)**, same prompt and same code validation for both models (`src/placewise/evals/extract.py`):

| Metric | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|
| Licenses + state exact match | 96.3% | **100%** |
| Flawed-resume precision | 57% | **94%** |
| Flawed-resume recall | 94% | 94% |
| Years MAE | 0.05 yr | 0.05 yr |
| Metro / discipline | 100% | 100% |
| Software | ~99–100% | ~99–100% |
| Cost per resume | $0.001 | $0.020 |

Haiku's errors: it dropped license states (an Arkansas PE stored as a stateless "PE"), added a TX PE once, and read the title "Civil Engineer in Training" as an EIT certification. Its low flawed precision would label many good resumes as flawed for recruiters.

## Alternatives considered
- **Haiku 5.5:** $0.001/resume, but licenses (the main hard filter) and quality labels are worse.
- **Hybrid:** Haiku extraction plus a Sonnet re-check of credentials only. Logged as a later cost optimization; needs its own eval.
- **Opus 5.5:** not needed; Sonnet already reaches 100% on licenses.

## Tradeoffs and consequences
- **Gain:** 100% license accuracy on dev, 94% flawed precision; end to end 99.7% licenses+state over all 597 resumes.
- **Give up:** ~$0.020 vs $0.001 per resume (about $12 for the whole 597-resume seed).
- **Revisit if:** volume makes cost matter (try the hybrid), a new Haiku closes the gap on the same eval, or real resumes change the picture.
