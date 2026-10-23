# Build Plan and Status

Rules: one block at a time → design approved → build → test → docs → check in. See `AGENTS.md`.
Status: ⬜ not started · 🟨 design proposed · 🟦 in progress · ✅ done

| # | Block | Delivers | Status |
|---|---|---|---|
| 0 | **Foundation** | Repo, agent context (AGENTS.md), GitHub, Docker Compose skeleton (db, api health, web hello), `.env` wiring, LangSmith connection check | ✅ merged (tag block-00-done) |
| 1 | **Synthetic data** | Facts generator (code) → resume text (LLM) → PDF/DOCX; job orders; ground-truth file; tricky cases | ✅ built, reviewed, tested, documented; owner approved merge |
| 2 | **Ingest pipeline** | DB migrations (schema as versioned migrations); ingest LangGraph (parse PDF/DOCX → extract profile → validate → blind copy → section chunks → Voyage embed → store), Postgres queue + worker, idempotency, LangSmith traces | 🟨 design approved by owner; starts after Block 1 merge |
| 3 | **Portal shell + auth** | Next.js app shell, login, admin/recruiter roles, Candidates list and profile pages | 🟦 portal shell (frontend only) in progress in parallel on block/03-portal-shell; auth + data wiring after Block 2 |
| 4 | **Job orders** | Notes → structured job order + clarifying questions; Job Orders pages | ⬜ |
| 5 | **Retrieval + RAG** | Hard filters + hybrid search + RRF + rerank; Ask page with cited answers | ⬜ |
| 6 | **Matching + approvals** | Match LangGraph (parallel scoring, evidence verification, code-computed score, blind scoring, flags) → submittals and outreach → approval interrupt; Shortlist and Approvals pages | ⬜ |
| 7 | **Recruiter agent** | LangGraph agent with tools, streaming chat UI, visible tool steps, step and cost limits | ⬜ |
| 8 | **n8n core** | Workflows 1 (resume intake), 4 (job order → match), 5 (approved → send to Mailpit); Apply page | ⬜ |
| 9 | **Evals, ops, polish** | LangSmith datasets and evaluators, Haiku vs Sonnet comparison, Ops dashboard, demo script, study guide, tunnel link | ⬜ |
| 10 | Stretch | Bench revival and MPC pitches; n8n workflows 2, 3, 6, 7 | ⬜ |
| 11 | Later: **Resume Generator v2** | Separate feature (owner, 2026-10-22): stronger writer model (Sonnet/Opus), more templates and human formatting quirks, visual quality check, "Show hidden text" view for adversarial files; possibly an admin "synthetic data studio" page. Block 1 ships a good-enough v1 so feature work isn't delayed. | ⬜ |

## Notes
- **Block 0 close-out (2026-10-22, branch `block/00-foundation` @ `0869213`, merged (tag block-00-done)):**
  - Design (db + api + web containers; status page with API ✓ DB ✓ LangSmith ✓) approved by the owner in chat; the design is recorded in `docs/modules/foundation.md`.
  - Built in `2fe7061`, reviewer fixes in `dc93a67`, QA tests plus the health-check lock in `4763e12`, docs in `0869213`.
  - Reviewer: APPROVE WITH FIXES, all fixes applied. Deferred: the web image runs as root (moves to Block 9). QA: PASS, 23 tests. UX review: not applicable, since the status page is a placeholder.
  - Done-when checked live: all 3 containers are up, `/api/health` returns 200 with all 3 checks ok, and `/docs`, `/openapi.json`, `/livez` and `/dev/trace` return 404 through :3000. Per the docs, a test trace reached the LangSmith project `placewise`.
  - Known gap: `web` has no Docker healthcheck, so it shows "Up" rather than "healthy".
  - Next: owner check-in → `git merge --no-ff block/00-foundation` → tag `block-00-done`.
- **Block 1 close-out (2026-10-22, branch `block/01-synthetic-data` @ `ba3470c`, merged (tag block-00-done); owner said "go ahead" to merge after close-out):**
  - Design (code facts → LLM writer with fact check → render → job orders + answer key → dev Seed page) approved by the owner in chat; recorded in `docs/modules/synthetic-data.md`. Owner-requested changes during the block: structured resumes, PDF-only showcase, in-page viewer, quality labels for deliberately bad resumes; Resume Generator v2 deferred to item 11.
  - Built in `2d69f13` (A), `e017977` (B), `2759f73`/`d4b4fa9` (C), `3800f47` (D); reviewer + QA fixes in `e6c6795`; docs in `7da7b8d` (module doc, seed pipeline diagram, ADRs 006–009, README); `ba3470c` removed an accidentally committed agent worktree pointer and ignores `.claude/worktrees/`.
  - Reviewer: APPROVE WITH FIXES; all 10 should-fix items fixed (`e6c6795`). Two nits left unfixed and documented in the module doc's known limits (candidate ids reveal generation order; conservative credential patterns). QA: PASS, 126 tests (23 Block 0 + 103 Block 1; command in README and module doc); QA's exact-duplicate-preview bug fixed and its xfail removed.
  - UX: the Seed page is a dev-only tool. No separate UX-reviewer agent was run; the owner reviewed the page directly and drove the viewer and quality-badge changes.
  - Data checked in the repo: 597 candidates / 597 resumes / 597 files (349 PDF, 190 DOCX, 58 TXT, plus 244 PDF previews); quality 519 polished / 65 flawed / 8 unusable / 5 adversarial; 15 job orders; JO-15 has 0 strong matches by design. Answer key isolation documented (ADR 008).
  - Live: db/api healthy, web up, `/seed` returns 200. No `.env` or worktree paths tracked.
  - Gaps: the build log has no entry for the worktree-pointer incident (`7da7b8d` → `ba3470c`).
  - Next: lead merges `git merge --no-ff block/01-synthetic-data` → tag `block-01-done` → Block 2.
- The early pre-design scaffold (`src/copilot/`: config, schemas, db, llm) was removed in Block 0. It's kept in git history at commit `8c55933` for reference when building blocks 2–6.
- The local `.venv` predates the folder rename and is not used. Everything runs in Docker. Safe to delete.
- 2026-10-22: the owner approved building the Block 3 portal shell (frontend only) in parallel with Block 2, in an isolated worktree on `block/03-portal-shell`, to have the UI sooner for the interview. Auth and data wiring stay in Block 3 after ingest.
