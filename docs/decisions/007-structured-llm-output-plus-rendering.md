# 007: Structured LLM output plus rendering instead of free-text parsing

- **Status:** accepted
- **Date:** 2026-10-22

## Context
Prompt versions v1–v3 of the resume writer returned free text (simple Markdown). The renderer had to guess which line was a heading, a job title, a company or a date. On owner review the results looked poor: projects as bare bullets, thin jobs, an odd "Sectors" section, broken layouts from heading-guessing, and the literal word "SIDEBAR" printed in two-column resumes. Checking facts in free text was also fragile.

## Decision
The writer returns a **Pydantic `StructuredResume`** via LangChain `with_structured_output(StructuredResume, include_raw=True)` (prompt v4, then v5): name, contact, headline, summary, jobs (title, employer, location, start, end, bullets), skills, credentials, education and optional extra sections, plus the headings to use.
- A **structural check** compares fields directly with the facts (exact title, employer and dates per job; exact credential list; exact education).
- `StructuredResume.to_text()` gives the plain text for the text fact check and TXT files.
- `seed/render.py` lays out the fields with five templates (classic, modern, two_column, compact, ats_plain) to PDF (ReportLab) and DOCX (python-docx). It never parses layout back out of text.
- Small, predictable schema slips are repaired rather than rejected (a validator flattens nested lists in extra sections, which caused 14 of 484 rejects once).

## Alternatives considered
- **Keep free text and improve heading detection:** fixed some cases but kept breaking on unusual headings, which we want on purpose.
- **Ask the LLM for HTML or Markdown and convert it:** still parsing model output for layout, and harder to fact-check per field.
- **LLM fills fixed templates field by field (many calls):** more calls and cost for the same result.

## Tradeoffs and consequences
- **Gain:** professional, consistent layouts; field-level fact checks; layout is fully controlled by code, so hard cases (two-column, hidden text, image-only, corrupt) are deliberate.
- **Give up:** variety is limited by our five templates and the schema's sections; real resumes have stranger structures. Schema validation can fail and costs a retry.
- **Revisit if:** Resume Generator v2 needs layouts the schema can't express. **Lesson that carries into ingest (Block 2):** prefer structured output and validate it, rather than parsing free text.
