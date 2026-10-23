# Build Plan and Status

Rules: one block at a time → design approved → build → test → docs → check in. See `AGENTS.md`.
Status: ⬜ not started · 🟨 design proposed · 🟦 in progress · ✅ done

| # | Block | Delivers | Status |
|---|---|---|---|
| 0 | **Foundation** | Repo, agent context (AGENTS.md), GitHub, Docker Compose skeleton (db, api health, web hello), `.env` wiring, LangSmith connection check | ✅ built, reviewed, tested, documented; awaiting owner check-in and merge |
| 1 | **Synthetic data** | Facts generator (code) → resume text (LLM) → PDF/DOCX; job orders; ground-truth file; tricky cases | ⬜ |
| 2 | **Ingest pipeline** | DB migrations (schema as versioned migrations); ingest LangGraph (parse PDF/DOCX → extract profile → validate → blind copy → section chunks → Voyage embed → store), Postgres queue + worker, idempotency, LangSmith traces | ⬜ |
| 3 | **Portal shell + auth** | Next.js app shell, login, admin/recruiter roles, Candidates list and profile pages | ⬜ |
| 4 | **Job orders** | Notes → structured job order + clarifying questions; Job Orders pages | ⬜ |
| 5 | **Retrieval + RAG** | Hard filters + hybrid search + RRF + rerank; Ask page with cited answers | ⬜ |
| 6 | **Matching + approvals** | Match LangGraph (parallel scoring, evidence verification, code-computed score, blind scoring, flags) → submittals and outreach → approval interrupt; Shortlist and Approvals pages | ⬜ |
| 7 | **Recruiter agent** | LangGraph agent with tools, streaming chat UI, visible tool steps, step and cost limits | ⬜ |
| 8 | **n8n core** | Workflows 1 (resume intake), 4 (job order → match), 5 (approved → send to Mailpit); Apply page | ⬜ |
| 9 | **Evals, ops, polish** | LangSmith datasets and evaluators, Haiku vs Sonnet comparison, Ops dashboard, demo script, study guide, tunnel link | ⬜ |
| 10 | Stretch | Bench revival and MPC pitches; n8n workflows 2, 3, 6, 7 | ⬜ |
| 11 | Later: **Resume Generator v2** | Separate feature (owner, 2026-10-22): stronger writer model (Sonnet/Opus), more templates and human formatting quirks, visual quality check, "Show hidden text" view for adversarial files; possibly an admin "synthetic data studio" page. Block 1 ships a good-enough v1 so feature work isn't delayed. | ⬜ |

## Notes
- **Block 0 close-out (2026-10-22, branch `block/00-foundation` @ `0869213`, not yet merged):**
  - Design (db + api + web containers; status page with API ✓ DB ✓ LangSmith ✓) approved by the owner in chat; the design is recorded in `docs/modules/foundation.md`.
  - Built in `2fe7061`, reviewer fixes in `dc93a67`, QA tests plus the health-check lock in `4763e12`, docs in `0869213`.
  - Reviewer: APPROVE WITH FIXES, all fixes applied. Deferred: the web image runs as root (moves to Block 9). QA: PASS, 23 tests. UX review: not applicable, since the status page is a placeholder.
  - Done-when checked live: all 3 containers are up, `/api/health` returns 200 with all 3 checks ok, and `/docs`, `/openapi.json`, `/livez` and `/dev/trace` return 404 through :3000. Per the docs, a test trace reached the LangSmith project `placewise`.
  - Known gap: `web` has no Docker healthcheck, so it shows "Up" rather than "healthy".
  - Next: owner check-in → `git merge --no-ff block/00-foundation` → tag `block-00-done`.
- The early pre-design scaffold (`src/copilot/`: config, schemas, db, llm) was removed in Block 0. It's kept in git history at commit `8c55933` for reference when building blocks 2–6.
- The local `.venv` predates the folder rename and is not used. Everything runs in Docker. Safe to delete.
