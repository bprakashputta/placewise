# Build Plan and Status

Rules: one block at a time → design approved → build → test → docs → check in. See `AGENTS.md`.
Status: ⬜ not started · 🟨 design proposed · 🟦 in progress · ✅ done

| # | Block | Delivers | Status |
|---|---|---|---|
| 0 | **Foundation** | Repo, agent context (AGENTS.md), GitHub, Docker Compose skeleton (db, api health, web hello), `.env` wiring, LangSmith connection check | ✅ merged (tag block-00-done) |
| 1 | **Synthetic data** | Facts generator (code) → resume text (LLM) → PDF/DOCX; job orders; ground-truth file; tricky cases | ✅ built, reviewed, tested, documented; owner approved merge |
| 2 | **Ingest pipeline** | DB migrations (schema as versioned migrations); ingest LangGraph (parse PDF/DOCX → extract profile → validate → blind copy → section chunks → Voyage embed → store), Postgres queue + worker, idempotency, LangSmith traces | ✅ merged ([PR #1](https://github.com/bprakashputta/placewise/pull/1), tag `block-02-done`) |
| 3 | **Portal shell + auth** | Next.js app shell, login, admin/recruiter roles, Candidates list and profile pages | ✅ merged (PR #2, tag `portal-v1`) |
| 4 | **Job orders** | Notes → structured job order + clarifying questions; Job Orders pages | ✅ merged (PR #2) |
| 5 | **Retrieval + RAG** | Hard filters + hybrid search + RRF + rerank; Ask page with cited answers | ✅ merged (PR #2); measured recall@10 89% ([module doc](modules/rag.md)) |
| 6 | **Matching + approvals** | Match LangGraph (parallel scoring, evidence verification, code-computed score, blind scoring, flags) → submittals and outreach → approval interrupt; Shortlist and Approvals pages | 🟦 scoring, shortlist, approve/reject and Approvals merged (PR #2; submit precision 97.6%); submittal/outreach drafts not yet |
| 7 | **Recruiter agent** | LangGraph agent with tools, streaming chat UI, visible tool steps, step and cost limits. Includes conversational Ask: route each message first (greeting/help/search/follow-up/job order/off-topic), saved conversations tied to job orders, Postgres checkpointer memory, routing evals ([ADR 018](decisions/018-conversational-ask-routing-and-threads.md)) | 🟦 conversational Ask merged (PR #2): routing 34/34, saved chats with the chat UI, follow-ups, job-order chats; tool-using agent still to design |
| 8 | **n8n core** | Workflows 1 (resume intake), 4 (job order → match), 5 (approved → send to Mailpit); Apply page | ⬜ |
| 9 | **Evals, ops, polish** | LangSmith datasets and evaluators, Haiku vs Sonnet comparison, Ops dashboard, demo script, study guide, tunnel link | 🟦 public link, cloud server and auto-deploy merged ([PR #5](https://github.com/bprakashputta/placewise/pull/5), tag `block-09-done`; [ADR 020](decisions/020-auto-deploy-main-to-cloud-server.md)); root redirect fix merged (PR #4). Still to do: LangSmith datasets/evaluators, Haiku vs Sonnet comparison, demo script, study guide |
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
- **Block 2 close-out (2026-10-22, branch `block/02-ingest` @ `8c9b7e7`, PR open: https://github.com/bprakashputta/placewise/pull/1):**
  - Design (Postgres `SKIP LOCKED` queue + worker service + LangGraph ingest graph + Sonnet extraction + code validation + chunks/Voyage embeddings + ingest/candidate APIs) approved by the owner in chat; recorded in `docs/modules/ingest.md` and ADRs 010–016. The owner chose Sonnet over Haiku after the dev-split eval (ADR 012). Owner-directed additions during the block: PR-based workflow with CI + Claude Code review (`9c7e7a9`); D2 diagrams instead of Mermaid (`be83e4c`, ADR 016); the spend cap (`DAILY_LLM_SPEND_CAP_USD`, an app setting the lead created, default $10) raised to $25 for the full ingest.
  - Built in `d48318d` (A: migrations, queue, worker), `02da54b` (B: parse + screen), `6c56f92` (C: extraction + validation + Haiku/Sonnet eval), `e821b74`/`d430668` (D: graph, chunks, embeddings, candidate API, spend-cap pause); fixes `1c86499` (pre-existing lint), `6c5c9b7` (person matching, dev reset, end-to-end eval).
  - Reviewer: CHANGES REQUIRED → 1 blocker + 9 should-fix, all fixed in `8fc541e`. QA: PASS WITH ISSUES → 4 bugs fixed in `b746cdd`; 246 unit tests + 24 DB integration tests (throwaway DB). UX review: not applicable (no UI in Block 2; the portal shell is on `block/03-portal-shell`).
  - Docs in `8c9b7e7`: `docs/modules/ingest.md`, ADRs 010–016, all diagrams in D2 with rendered SVGs (no Mermaid left in docs), README; build-log Block 2 entries present.
  - Evals (stored data vs answer key): routing 597/597, licenses+state 99.7%, people 563 = 563, unusable/adversarial 100%, flawed 88% precision / 92% recall, cost $12.23 total.
  - Live: api + db healthy, 3 workers up, web up; `/api/ingest/summary` → done 583, duplicate 8, needs_attention 8. No `.env` or worktree paths tracked. CI at close-out: GitGuardian passed; backend tests, web lint + build and Claude Code review still running.
  - Minor gaps: build log says ~$12.12 and "581 processed" vs $12.23 (likely incl. the $0.11 re-ingest) and 583 done live (likely QA/upload test jobs); `.env.example` still shows the $10 default (intended).
  - Next: wait for CI + Claude review on PR #1, fix findings → owner approves the PR → `git merge --no-ff block/02-ingest` → tag `block-02-done` → Block 3 auth + data wiring.
- **Block 9 notes:**
  - ✅ Public spend cap set to $10/day on the cloud server (`PUBLIC_DAILY_LLM_SPEND_CAP_USD`).
  - ⬜ LangSmith: hide inputs/outputs for any real data. Open: the owner added a few real resumes for testing, and their text appears in LangSmith traces.
  - Hosting: Google Cloud VM `placewise-vm` (project `placewise-demo-1023`), about $0.85/day from the free credit; delete it (and the `placewise-ip` address) when the demo ends.
- The early pre-design scaffold (`src/copilot/`: config, schemas, db, llm) was removed in Block 0. It's kept in git history at commit `8c55933` for reference when building blocks 2–6.
- The local `.venv` predates the folder rename and is not used. Everything runs in Docker. Safe to delete.
- 2026-10-22: the owner approved building the Block 3 portal shell (frontend only) in parallel with Block 2, in an isolated worktree on `block/03-portal-shell`, to have the UI sooner for the interview. Auth and data wiring stay in Block 3 after ingest.
