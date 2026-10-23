# Sequence: Synthetic data pipeline (Block 1)

How the seed CLI turns code-generated facts into resume files, job orders and an answer key, and how the dev-only Seed page shows the result. Code: `src/placewise/seed/` (`__main__.py`, `facts.py`, `writer.py`, `factcheck.py`, `noise.py`, `render.py`, `job_orders.py`, `public.py`), `src/placewise/dev_seed.py`, `web/src/app/seed/`.

```mermaid
sequenceDiagram
    autonumber
    actor O as Owner
    participant S as seed container (CLI)
    participant H as Claude Haiku 5.5
    participant T as data/seed/truth
    participant G as generated + resumes
    participant P as data/seed/public
    participant A as api (dev only)
    participant W as Seed page

    O->>S: facts --count 500 --seed 42
    S->>T: candidates.jsonl (ground truth, no LLM)
    O->>S: write
    loop each candidate, max 3 attempts
        S->>H: facts for writer + prompt v5
        H-->>S: StructuredResume
        S->>S: structural check + text fact check
        Note over S: on failure, retry with the problems listed
    end
    S->>G: resumes.jsonl (accepted only)
    O->>S: render
    S->>S: code noise (bullets, flagged typos)
    S->>G: PDF / DOCX / TXT + previews + files.jsonl
    O->>S: job-orders
    S->>T: targeted candidates, job_orders.jsonl
    S->>H: spec as required / preferred / nice to have
    H-->>S: recruiter call notes
    S->>T: relevance.jsonl (graded from facts)
    S->>P: publish aggregates + dev-split showcase
    W->>A: GET /api/dev/seed/status (polls)
    A->>P: read (ro)
    A-->>W: progress, stats, showcase, job orders
    W->>A: GET /api/dev/seed/files/{id}/view
    A->>G: read resumes/ (ro)
    A-->>W: PDF shown in the in-page viewer
```

## Key points
- **Truth first, text second.** Facts and the answer key come from code; the LLM only writes prose around them, and the checks make sure the text agrees ([ADR 006](../decisions/006-synthetic-data-code-facts-as-ground-truth.md)).
- **Structured output, then render.** The writer returns fields, not free text, so the renderer never guesses layout ([ADR 007](../decisions/007-structured-llm-output-plus-rendering.md)).
- **The api never sees `truth/`.** It reads only `public/` and `resumes/` (and `outputs/samples/`), read-only, and its seed routes exist only when `APP_ENV=dev` ([ADR 008](../decisions/008-answer-key-isolation.md)).
- After `job-orders`, run `write` and `render` again to produce the 97 targeted resumes (not shown).
- `publish` also runs at the end of `facts` and `render`; `write` updates `public/progress.json` live.

See also: [Synthetic data module](../modules/synthetic-data.md) · [architecture](architecture.md)
