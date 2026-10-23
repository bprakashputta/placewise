# Build Plan and Status

Rules: one block at a time → design approved → build → test → docs → check in. See `AGENTS.md`.
Status: ⬜ not started · 🟨 design proposed · 🟦 in progress · ✅ done

| # | Block | Delivers | Status |
|---|---|---|---|
| 0 | **Foundation** | Repo, agent context (AGENTS.md), GitHub, Docker Compose skeleton (db, api health, web hello), `.env` wiring, LangSmith connection check | 🟦 built; reviewer fixes in progress |
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

## Notes
- The early pre-design scaffold (`src/copilot/`: config, schemas, db, llm) was removed in Block 0. It's kept in git history at commit `8c55933` for reference when building blocks 2–6.
- The local `.venv` predates the folder rename and is not used. Everything runs in Docker. Safe to delete.
