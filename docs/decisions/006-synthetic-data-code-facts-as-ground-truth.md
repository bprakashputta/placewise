# 006: Synthetic data with code-generated facts as ground truth

- **Status:** accepted
- **Date:** 2026-10-22

## Context
Placewise must be built and evaluated without real people's resumes (AGENTS.md: synthetic data only). Later blocks need to measure extraction accuracy and match quality, which needs a known correct answer for every resume and every (job order, candidate) pair. If an LLM invented both the resume and the "truth", we couldn't tell its mistakes apart from the truth.

## Decision
**Code decides every fact first; the LLM only writes the resume around those facts.**
- `seed/facts.py` generates `CandidateFacts` with a fixed seed (42) and a fixed date (`AS_OF = 2026-10-22`): identity, jobs and dates, credentials with status and held/not held, software, sectors, education, style and tricky cases. The same command always produces the same 474 base people (plus duplicates, updates and 97 targeted candidates: 597 in total).
- Code also chooses the **exact phrasing** of credentials and dates (e.g. `P.E., Texas #123456` vs `Licensed PE - Texas`), and the writer must copy it.
- Fact checks (structural + text) reject any resume that omits a fact or invents a credential, tool or license state; up to 2 retries with feedback. 597/597 pass.
- The answer key (`relevance.jsonl`, `quality` labels, `license_codes`) is computed **from the facts**, never from the generated text.
- Split by person: about 30% dev / 70% test.

## Alternatives considered
- **LLM generates whole resumes, then we label them by hand:** slow, and hand labels for 600 resumes would be error-prone.
- **LLM generates resumes, and another LLM extracts the "truth":** circular. It would measure model agreement, not correctness.
- **Public resume datasets:** real people's data (not allowed), rarely A/E/C, and no reliable labels for license state or status.
- **Template-only resumes with no LLM:** perfect truth, but too uniform; extraction would look trivially easy.

## Tradeoffs and consequences
- **Gain:** a known answer for every field and pair; reproducible; cheap (under $1 of LLM spend for all 597 resumes); tricky cases are planted on purpose and labeled.
- **Give up:** the data is cleaner and less varied than real resumes, so accuracy on it is an **optimistic upper bound**. The fact checks constrain the writer, which limits how "human" the prose can get.
- **Revisit if:** we get permission to use a real, labeled sample, or Resume Generator v2 (PLAN item 11) adds enough variety to change the picture.
